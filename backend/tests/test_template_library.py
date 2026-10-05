"""
Integration tests for the template library endpoints.
V1.2 Phase 3 — Member 3
"""
import io
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
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
        app.dependency_overrides.pop(get_db, None)


def _signup_and_login(email: str, full_name: str) -> str:
    """Sign up a user and return their auth token."""
    client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": full_name,
            "email": email,
            "password": "strong-password",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    return login.json()["access_token"]


def _upload_template(token: str, name: str, category: str, visibility: str) -> dict:
    """Upload a template via API and return the response JSON."""
    files = {
        "file": (
            "template.docx",
            io.BytesIO(b"fake content"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"name": name, "category": category, "visibility": visibility}
    response = client.post(
        "/api/v1/templates/upload",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, f"Upload failed: {response.json()}"
    return response.json()


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def user_a_token():
    return _signup_and_login("library_a@example.com", "Library User A")


@pytest.fixture(scope="module")
def user_b_token():
    return _signup_and_login("library_b@example.com", "Library User B")


@pytest.fixture(scope="module")
def seed_templates(user_a_token, user_b_token):
    """
    Upload test templates for User A and User B.
    Returns a dict mapping template names to their IDs.
    """
    templates = {}

    # User A uploads 3 templates
    templates["Notice Template"] = _upload_template(
        user_a_token, "Notice Template", "notice", "public"
    )
    templates["Private Report"] = _upload_template(
        user_a_token, "Private Report", "report", "private"
    )
    templates["Meeting MoM"] = _upload_template(
        user_a_token, "Meeting MoM", "mom", "public"
    )

    # User B uploads 2 templates
    templates["B's Application"] = _upload_template(
        user_b_token, "B's Application", "application", "public"
    )
    templates["B's Private Letter"] = _upload_template(
        user_b_token, "B's Private Letter", "letter", "private"
    )

    return templates


# ── Library endpoint tests ────────────────────────────────────────

def test_library_returns_own_and_public(user_a_token, seed_templates):
    """User A should see their own 3 templates + B's 1 public, NOT B's private."""
    response = client.get(
        "/api/v1/templates/library",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 4

    names = [t["name"] for t in data["templates"]]
    assert "Notice Template" in names
    assert "Private Report" in names  # own private
    assert "Meeting MoM" in names
    assert "B's Application" in names  # B's public
    assert "B's Private Letter" not in names  # B's private — must NOT appear


def test_library_search_by_name(user_a_token, seed_templates):
    """Searching for 'notice' should return templates with 'notice' in the name."""
    response = client.get(
        "/api/v1/templates/library?search=notice",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for t in data["templates"]:
        assert "notice" in t["name"].lower()


def test_library_filter_by_category(user_a_token, seed_templates):
    """Filtering by category=notice should return only notice templates."""
    response = client.get(
        "/api/v1/templates/library?category=notice",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for t in data["templates"]:
        assert t["category"] == "notice"


def test_library_filter_by_visibility(user_a_token, seed_templates):
    """Filtering by visibility=public should return only public templates."""
    response = client.get(
        "/api/v1/templates/library?visibility=public",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for t in data["templates"]:
        assert t["visibility"] == "public"


def test_library_filter_by_visibility_private(user_a_token, seed_templates):
    """Filtering visibility=private should show only User A's private templates, not B's."""
    response = client.get(
        "/api/v1/templates/library?visibility=private",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    names = [t["name"] for t in data["templates"]]
    # User A's private should appear
    assert "Private Report" in names
    # User B's private must NOT appear
    assert "B's Private Letter" not in names
    # All returned templates must be private
    for t in data["templates"]:
        assert t["visibility"] == "private"


def test_library_pagination(user_a_token, seed_templates):
    """Pagination should limit results per page but report the full total."""
    response = client.get(
        "/api/v1/templates/library?page=1&limit=2",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["templates"]) <= 2
    assert data["total"] >= 4  # full count, not limited to page
    assert data["page"] == 1
    assert data["limit"] == 2


def test_library_combined_filters(user_a_token, seed_templates):
    """Combining category + visibility should return templates matching both."""
    response = client.get(
        "/api/v1/templates/library?category=notice&visibility=public",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for t in data["templates"]:
        assert t["category"] == "notice"
        assert t["visibility"] == "public"


@pytest.mark.parametrize("bad_category", ["invalid_xyz", "foo", "bar123"])
def test_library_invalid_category_filter(user_a_token, bad_category):
    """Invalid category values should return 400."""
    response = client.get(
        f"/api/v1/templates/library?category={bad_category}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 400


@pytest.mark.parametrize("bad_visibility", ["invalid_xyz", "foo", "bar123"])
def test_library_invalid_visibility_filter(user_a_token, bad_visibility):
    """Invalid visibility values should return 400."""
    response = client.get(
        f"/api/v1/templates/library?visibility={bad_visibility}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 400


def test_library_unauthenticated():
    """Requests without auth should be rejected."""
    response = client.get("/api/v1/templates/library")
    assert response.status_code in (401, 403)


# ── Detail endpoint visibility tests ────────────────────────────

def test_detail_public_template_accessible_by_other_user(user_b_token, seed_templates):
    """User B should be able to view User A's public template."""
    template_id = seed_templates["Notice Template"]["id"]
    response = client.get(
        f"/api/v1/templates/{template_id}",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Notice Template"


def test_detail_private_template_not_accessible_by_other_user(user_b_token, seed_templates):
    """User B should NOT be able to view User A's private template."""
    template_id = seed_templates["Private Report"]["id"]
    response = client.get(
        f"/api/v1/templates/{template_id}",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert response.status_code == 403
