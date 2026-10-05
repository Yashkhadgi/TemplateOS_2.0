"""
Tests for super-admin template deletion.
V1.3 — DELETE /api/v1/templates/{id}

Rules under test:
- Super-admin only: regular users (even the template OWNER) get 403.
- The DB record is removed and template_fields cascade away.
- Stored files (original + processed) are removed from disk.
- 404 for a missing template; idempotent 404 after a successful delete.
"""

import io
import os

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.template import Template
from app.models.template_field import TemplateField
from app.services.storage_service import storage_service

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    with TestSession() as db:
        yield db


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    old = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if old is not None:
        app.dependency_overrides[get_db] = old
    else:
        app.dependency_overrides.pop(get_db, None)


def _signup_and_login(email: str, full_name: str) -> str:
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": full_name, "email": email, "password": "strong-password"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    return login.json()["access_token"]


@pytest.fixture(scope="module")
def owner_token():
    return _signup_and_login("delete_owner@example.com", "Delete Owner")


@pytest.fixture(scope="module")
def other_token():
    return _signup_and_login("delete_other@example.com", "Delete Other")


@pytest.fixture(scope="module")
def super_admin_token():
    token = _signup_and_login("delete_admin@example.com", "Delete Admin")
    # Promote to super_admin directly in the DB (signup defaults to a normal role).
    with TestSession() as session:
        from app.models.user import User

        user = (
            session.query(User).filter(User.email == "delete_admin@example.com").one()
        )
        user.role = "super_admin"
        session.commit()
    return token


def _build_docx(paragraph_text: str = "Notice for {{sample_key}}") -> bytes:
    document = Document()
    document.add_paragraph(paragraph_text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _upload_template(token: str, name: str, docx_bytes: bytes | None = None) -> dict:
    files = {
        "file": (
            "sample.docx",
            io.BytesIO(docx_bytes or _build_docx()),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"name": name, "category": "notice", "visibility": "private"}
    response = client.post(
        "/api/v1/templates/upload",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, f"Upload failed: {response.json()}"
    return response.json()


def _add_field(template_id: int) -> None:
    with TestSession() as session:
        session.add(
            TemplateField(
                template_id=template_id,
                field_name="sample_key",
                field_label="Sample Key",
            )
        )
        session.commit()


def _db_template_exists(template_id: int) -> bool:
    with TestSession() as session:
        return session.get(Template, template_id) is not None


def _db_fields_count(template_id: int) -> int:
    with TestSession() as session:
        return (
            session.query(TemplateField)
            .filter(TemplateField.template_id == template_id)
            .count()
        )


def test_super_admin_deletes_template_record_and_files(super_admin_token, owner_token):
    template = _upload_template(owner_token, "Delete Happy Path")
    template_id = template["id"]
    _add_field(template_id)

    original_path = template["original_file_path"]
    assert storage_service.exists(original_path)

    response = client.delete(
        f"/api/v1/templates/{template_id}",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 204
    assert response.content == b""  # no body on 204

    # DB record gone, fields cascaded.
    assert _db_template_exists(template_id) is False
    assert _db_fields_count(template_id) == 0

    # Original file removed from storage.
    assert storage_service.exists(original_path) is False

    # Subsequent reads 404.
    detail = client.get(
        f"/api/v1/templates/{template_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detail.status_code == 404


def test_delete_also_removes_processed_file(super_admin_token, owner_token):
    template = _upload_template(owner_token, "Delete With Processed")
    template_id = template["id"]

    # Create a processed copy via the cleaning endpoint.
    clean = client.post(
        f"/api/v1/templates/{template_id}/clean",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "replacements": [
                {"sample_text": "{{sample_key}}", "placeholder_key": "never_matches"}
            ],
            "confirm": True,
        },
    )
    assert clean.status_code == 200
    processed_path = clean.json()["processed_file_path"]
    assert storage_service.exists(processed_path)

    response = client.delete(
        f"/api/v1/templates/{template_id}",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 204
    assert storage_service.exists(processed_path) is False
    assert storage_service.exists(template["original_file_path"]) is False


def test_owner_cannot_delete_own_template(owner_token):
    template = _upload_template(owner_token, "Delete By Owner")
    response = client.delete(
        f"/api/v1/templates/{template['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 403
    assert "super admin" in response.json()["detail"].lower()
    assert _db_template_exists(template["id"]) is True


def test_other_user_cannot_delete(other_token, owner_token):
    template = _upload_template(owner_token, "Delete By Other")
    response = client.delete(
        f"/api/v1/templates/{template['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403
    assert _db_template_exists(template["id"]) is True


def test_delete_missing_template_404(super_admin_token):
    response = client.delete(
        "/api/v1/templates/999999",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 404


def test_delete_requires_auth():
    response = client.delete("/api/v1/templates/1")
    assert response.status_code == 401


def test_deleted_template_is_gone_forever(super_admin_token, owner_token):
    """Deleting twice: the second attempt 404s (already gone)."""
    template = _upload_template(owner_token, "Delete Twice")
    first = client.delete(
        f"/api/v1/templates/{template['id']}",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert first.status_code == 204
    second = client.delete(
        f"/api/v1/templates/{template['id']}",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert second.status_code == 404
