import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests")

from fastapi.testclient import TestClient
import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    with TestSession() as db:
        yield db


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def test_signup_login_and_profile_flow() -> None:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Test User",
            "email": "Test@Example.com",
            "password": "strong-password",
        },
    )
    assert signup.status_code == 201
    assert signup.json()["email"] == "test@example.com"
    assert signup.json()["role"] == "normal_user"
    assert "hashed_password" not in signup.json()

    with Session(test_engine) as db:
        user = db.scalar(select(User).where(User.email == "test@example.com"))
        assert user is not None
        assert user.hashed_password is not None
        assert user.hashed_password != "strong-password"

    duplicate = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Duplicate",
            "email": "TEST@example.com",
            "password": "another-password",
        },
    )
    assert duplicate.status_code == 409

    rejected = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrong-password"},
    )
    assert rejected.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "strong-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    profile = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    expired_token = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    expired = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired.status_code == 401
    assert profile.status_code == 200
    profile_body = profile.json()
    assert profile_body == {
        "id": user.id,
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "normal_user",
        "department": None,
        "organization": None,
        "job_title": None,
        "phone": None,
        "avatar_url": None,
        "signature_path": None,
        "preferences": None,
    }
    assert "hashed_password" not in profile_body


def test_profile_rejects_missing_and_invalid_tokens() -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    invalid = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert invalid.status_code == 401


def test_profile_rejects_token_for_missing_user() -> None:
    token = jwt.encode(
        {
            "sub": "999",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
