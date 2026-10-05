import io
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure we're using a dummy DB and secret
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests")

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.template import Template

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
        del app.dependency_overrides[get_db]

@pytest.fixture(scope="module")
def auth_token():
    # create a user
    client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Upload User",
            "email": "upload@example.com",
            "password": "strong-password",
        },
    )
    # login to get token
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "upload@example.com", "password": "strong-password"},
    )
    return login.json()["access_token"]

@pytest.fixture(autouse=True)
def clear_templates():
    # We want to clear templates after each test to avoid interference
    yield
    with TestSession() as db:
        for t in db.execute(select(Template)).scalars().all():
            db.delete(t)
        db.commit()


# Tests
def test_upload_valid_docx(auth_token):
    files = {"file": ("template.docx", io.BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 201
    res_json = response.json()
    assert "id" in res_json
    assert res_json["status"] == "uploaded"
    assert isinstance(res_json["original_file_path"], str)
    assert res_json["original_file_path"].endswith(".docx")

def test_upload_invalid_extension(auth_token):
    files = {"file": ("document.pdf", io.BytesIO(b"fake content"), "application/pdf")}
    data = {"name": "Test Template", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400
    assert "docx" in response.json()["detail"].lower()

def test_upload_file_too_large(auth_token):
    large_content = b"a" * (11 * 1024 * 1024)
    files = {"file": ("big.docx", io.BytesIO(large_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400
    assert "10 mb" in response.json()["detail"].lower() or "size" in response.json()["detail"].lower()

def test_upload_empty_file(auth_token):
    files = {"file": ("empty.docx", io.BytesIO(b""), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400

@pytest.mark.parametrize("category", ["invalid_xyz"])
def test_upload_invalid_category(auth_token, category):
    files = {"file": ("template.docx", io.BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": category, "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400

@pytest.mark.parametrize("visibility", ["invalid_xyz"])
def test_upload_invalid_visibility(auth_token, visibility):
    files = {"file": ("template.docx", io.BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": "notice", "visibility": visibility}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400

def test_upload_missing_name(auth_token):
    files = {"file": ("template.docx", io.BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400

def test_upload_unauthenticated():
    files = {"file": ("template.docx", io.BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data)
    assert response.status_code in (401, 403)

def test_upload_path_is_string_not_binary(auth_token):
    files = {"file": ("template.docx", io.BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test Template", "category": "notice", "visibility": "private"}
    response = client.post("/api/v1/templates/upload", files=files, data=data, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 201

    with TestSession() as db:
        template = db.query(Template).order_by(Template.created_at.desc()).first()
        assert isinstance(template.original_file_path, str) is True
        assert not template.original_file_path.startswith("b'")
        assert len(template.original_file_path) < 500
