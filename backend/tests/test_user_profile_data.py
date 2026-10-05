import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-data-tests")

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.db.base import Base
from app.db.demo_seed import (
    DEMO_USER_DEFINITIONS,
    DemoUserSeed,
    build_demo_user_seeds,
    seed_demo_users,
)
from app.db.session import get_db
from app.main import app
from app.models.user import USER_ROLES, User


@pytest.fixture()
def engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_profile_fields_persist_and_optional_fields_remain_nullable(engine) -> None:
    with Session(engine) as db:
        profile = User(
            email="faculty-profile@example.com",
            full_name="Faculty Profile",
            role="faculty",
            hashed_password="stored-hash",
            department="Computer Science",
            organization="TemplateOS Demo Institute",
            job_title="Assistant Professor",
            phone="+91 00000 00000",
            avatar_url="/avatars/faculty.png",
            signature_path="/signatures/faculty.png",
            preferences={
                "default_document_format": "docx",
                "email_notifications": False,
            },
        )
        minimal = User(email="minimal@example.com", full_name="Minimal User")
        db.add_all((profile, minimal))
        db.commit()
        profile_id = profile.id
        minimal_id = minimal.id

    with Session(engine) as db:
        stored_profile = db.get(User, profile_id)
        assert stored_profile is not None
        assert stored_profile.department == "Computer Science"
        assert stored_profile.organization == "TemplateOS Demo Institute"
        assert stored_profile.job_title == "Assistant Professor"
        assert stored_profile.phone == "+91 00000 00000"
        assert stored_profile.avatar_url == "/avatars/faculty.png"
        assert stored_profile.signature_path == "/signatures/faculty.png"
        assert stored_profile.preferences == {
            "default_document_format": "docx",
            "email_notifications": False,
        }

        stored_minimal = db.get(User, minimal_id)
        assert stored_minimal is not None
        assert stored_minimal.role == "normal_user"
        assert stored_minimal.department is None
        assert stored_minimal.organization is None
        assert stored_minimal.job_title is None
        assert stored_minimal.phone is None
        assert stored_minimal.avatar_url is None
        assert stored_minimal.signature_path is None
        assert stored_minimal.preferences is None


def test_invalid_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported user role"):
        User(
            email="invalid-role@example.com",
            full_name="Invalid Role",
            role="owner",
        )


def test_email_uniqueness_remains_enforced(engine) -> None:
    with Session(engine) as db:
        db.add(User(email="unique@example.com", full_name="First User"))
        db.commit()
        db.add(User(email="unique@example.com", full_name="Second User"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_demo_seed_is_idempotent_and_hashes_passwords(engine) -> None:
    password = "fixture-password"
    seed = DemoUserSeed(
        email=" Faculty.Demo@Example.com ",
        password=password,
        full_name="Demo Faculty",
        role="faculty",
        department="Computer Science",
        organization="TemplateOS Demo Institute",
        job_title="Assistant Professor",
        preferences={
            "default_document_format": "docx",
            "email_notifications": False,
        },
    )

    with Session(engine) as db:
        first_users = seed_demo_users(db, (seed,))
        first_id = first_users[0].id
        first_hash = first_users[0].hashed_password
        second_users = seed_demo_users(db, (seed,))

        assert second_users[0].id == first_id
        assert second_users[0].hashed_password == first_hash
        assert db.scalars(select(User)).all() == second_users
        assert first_hash is not None
        assert first_hash != password
        assert verify_password(password, first_hash)
        assert second_users[0].email == "faculty.demo@example.com"
        assert second_users[0].department == "Computer Science"


def test_configured_demo_accounts_cover_supported_roles() -> None:
    values: dict[str, str] = {}
    for index, definition in enumerate(DEMO_USER_DEFINITIONS):
        values[f"{definition.environment_prefix}_EMAIL"] = (
            f"demo-{index}@example.com"
        )
        values[f"{definition.environment_prefix}_PASSWORD"] = (
            f"fixture-password-{index}"
        )

    seeds = build_demo_user_seeds(values)

    assert len(seeds) == len(USER_ROLES)
    assert tuple(seed.role for seed in seeds) == USER_ROLES

    assert all(
        definition.environment_prefix.startswith("SIT_")
        for definition in DEMO_USER_DEFINITIONS
    )


def test_env_example_matches_demo_seed_credential_names() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    example_values = dotenv_values(root_dir / ".env.example")
    legacy_prefix = "".join(("TEM", "P_"))
    expected_names = {
        f"{definition.environment_prefix}_{suffix}"
        for definition in DEMO_USER_DEFINITIONS
        for suffix in ("EMAIL", "PASSWORD")
    }

    assert expected_names <= example_values.keys()
    assert not any(name.startswith(legacy_prefix) for name in example_values)


def test_seeded_demo_user_authenticates_with_normal_login(engine) -> None:
    password = "demo-login-password"
    seed = DemoUserSeed(
        email="demo-login@example.com",
        password=password,
        full_name="Demo Login",
        role="student",
        department="Computer Science",
        organization="TemplateOS Demo Institute",
        job_title="Student",
    )
    with Session(engine) as db:
        seed_demo_users(db, (seed,))

    def override_get_db():
        with Session(engine) as db:
            yield db

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/api/v1/auth/login",
            json={"email": seed.email, "password": password},
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_profile_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    database_path = (tmp_path / "profile-migration.db").as_posix()
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database_path}",
        "JWT_SECRET_KEY": "test-secret-that-is-long-enough-for-migration-tests",
    }
    command = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        "alembic.ini.example",
    ]

    subprocess.run(
        [*command, "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    migration_engine = create_engine(environment["DATABASE_URL"])
    expected_columns = {
        "department",
        "organization",
        "job_title",
        "phone",
        "avatar_url",
        "signature_path",
        "preferences",
    }
    assert expected_columns <= {
        column["name"] for column in inspect(migration_engine).get_columns("users")
    }

    subprocess.run(
        [*command, "downgrade", "20260719_02"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert expected_columns.isdisjoint(
        column["name"] for column in inspect(migration_engine).get_columns("users")
    )
    migration_engine.dispose()
