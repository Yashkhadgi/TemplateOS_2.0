"""
Data-layer tests for the V1.3 Phase 4 AI audit trail.
Member 3 — Database / Integration Developer

Layers:
1. Model/CRUD: log_ai_generation writes lean metadata rows (success AND
   error); the custom __init__ defaults status="success" pre-flush;
   @validates rejects unknown statuses; get_ai_generations_by_template
   returns newest first (created_at desc, id desc) and honors its limit.
2. FK behavior: deleting a template SET NULLs ai_generations.template_id
   (the chosen behavior — audit rows survive template deletion), while
   deleting the acting user CASCADEs the rows away.
3. Migration: upgrade head creates ai_generations with the lean column
   set, both FKs (template SET NULL, created_by CASCADE) and both
   indexes; downgrade to its parent drops it; upgrade head again works.
   FK clauses are behaviorally verified on the migration-created scratch
   DB with PRAGMA foreign_keys=ON (alembic via subprocess).

The engine enables SQLite FK enforcement so ON DELETE clauses actually
fire in tests (they are enforced by default on PostgreSQL/Neon).
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)
# No model id is hardcoded in app code — tests provide one like .env would.
os.environ.setdefault("BEDROCK_MODEL_SUGGESTIONS", "test-model-id")

# Single test-wide constant (matches the env value above) so no real Bedrock
# model id is hardcoded anywhere in the test suite.
TEST_MODEL_ID = "test-model-id"

from app.crud.ai_generation_crud import (
    get_ai_generations_by_template,
    log_ai_generation,
)
from app.db.base import Base
from app.models.ai_generation import AiGeneration
from app.models.template import Template
from app.models.user import User

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    """Function-scoped session for direct CRUD tests (isolated per test)."""
    session = TestSession()
    yield session
    session.rollback()
    session.close()


USER_EMAIL = "ai_audit_owner@example.com"


def _make_user(db, email: str) -> User:
    user = User(email=email, full_name="AI Audit Owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_template(db, name: str, uploaded_by: int) -> Template:
    template = Template(
        name=name,
        category="mom",
        visibility="private",
        uploaded_by=uploaded_by,
        status="placeholder_detected",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


# ── 1. Model / CRUD ─────────────────────────────────────────────────


def test_log_ai_generation_writes_row_with_metadata(db):
    user = _make_user(db, "ai_log_owner@example.com")
    template = _make_template(db, "AI Log Template", user.id)

    row = log_ai_generation(
        db,
        action_type="suggest_fields",
        model=TEST_MODEL_ID,
        template_id=template.id,
        created_by=user.id,
        suggestions_count=3,
    )

    assert row.id is not None
    assert row.action_type == "suggest_fields"
    assert row.model == TEST_MODEL_ID
    assert row.template_id == template.id
    assert row.created_by == user.id
    assert row.status == "success"
    assert row.suggestions_count == 3
    assert row.document_id is None  # reserved for V1.4, no FK
    assert row.detail is None
    assert row.created_at is not None

    # Committed: visible from a fresh session.
    fresh = TestSession()
    try:
        persisted = fresh.get(AiGeneration, row.id)
        assert persisted is not None
        assert persisted.action_type == "suggest_fields"
        assert persisted.status == "success"
    finally:
        fresh.close()


def test_log_ai_generation_error_row(db):
    user = _make_user(db, "ai_error_owner@example.com")

    row = log_ai_generation(
        db,
        action_type="suggest_fields",
        model=TEST_MODEL_ID,
        created_by=user.id,
        status="error",
        suggestions_count=0,
        detail="AI is not configured",
    )

    assert row.status == "error"
    assert row.detail == "AI is not configured"
    assert row.template_id is None


def test_default_status_pre_flush_via_custom_init():
    gen = AiGeneration(action_type="suggest_fields", model="m", created_by=1)
    assert gen.status == "success"  # pre-flush, mirrors Template.__init__


def test_orm_rejects_invalid_status():
    with pytest.raises(ValueError):
        AiGeneration(
            action_type="suggest_fields", model="m", created_by=1, status="pending"
        )


def test_get_ai_generations_by_template_newest_first(db):
    user = _make_user(db, "ai_order_owner@example.com")
    template = _make_template(db, "AI Order Template", user.id)

    first = log_ai_generation(
        db,
        action_type="suggest_fields",
        model="m",
        template_id=template.id,
        created_by=user.id,
        suggestions_count=1,
    )
    second = log_ai_generation(
        db,
        action_type="suggest_fields",
        model="m",
        template_id=template.id,
        created_by=user.id,
        suggestions_count=2,
    )
    third = log_ai_generation(
        db,
        action_type="improve_writing",
        model="m",
        template_id=template.id,
        created_by=user.id,
        status="error",
    )

    # SQLite CURRENT_TIMESTAMP is second-resolution: pin distinct timestamps
    # so created_at desc is actually exercised (id desc is the tiebreaker).
    first.created_at = datetime(2026, 1, 1, 10, 0, 0)
    second.created_at = datetime(2026, 1, 1, 10, 0, 5)
    third.created_at = datetime(2026, 1, 1, 10, 0, 5)  # same second as second
    db.commit()

    rows = get_ai_generations_by_template(db, template.id)
    # newest first; same created_at -> higher id first
    assert [row.id for row in rows] == [third.id, second.id, first.id]

    # limit is honored (still newest first)
    limited = get_ai_generations_by_template(db, template.id, limit=2)
    assert [row.id for row in limited] == [third.id, second.id]

    # other templates' rows do not leak in
    other = _make_template(db, "AI Other Template", user.id)
    assert get_ai_generations_by_template(db, other.id) == []


# ── 2. FK behavior (SQLite FKs enforced via PRAGMA) ─────────────────


def test_deleting_template_set_nulls_template_id(db):
    user = _make_user(db, "ai_setnull_owner@example.com")
    template = _make_template(db, "AI SetNull Template", user.id)
    row = log_ai_generation(
        db,
        action_type="suggest_fields",
        model="m",
        template_id=template.id,
        created_by=user.id,
        suggestions_count=2,
    )

    db.delete(template)
    db.commit()
    db.expire_all()

    survived = db.get(AiGeneration, row.id)
    # Chosen behavior: SET NULL — the audit trail survives template deletion.
    assert survived is not None
    assert survived.template_id is None
    assert survived.status == "success"


def test_deleting_user_cascades_ai_generations(db):
    user = _make_user(db, "ai_cascade_owner@example.com")
    template = _make_template(db, "AI Cascade Template", user.id)
    row = log_ai_generation(
        db,
        action_type="suggest_fields",
        model="m",
        template_id=template.id,
        created_by=user.id,
    )
    generation_id = row.id

    db.delete(template)
    db.delete(user)
    db.commit()
    db.expire_all()

    assert db.get(AiGeneration, generation_id) is None


# ── 3. Migration: upgrade head / downgrade to parent / upgrade again ──


def test_ai_generations_migration_up_down_up(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    database_path = (tmp_path / "ai-generations.db").as_posix()
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database_path}",
        "JWT_SECRET_KEY": "test-secret-that-is-long-enough-for-migration-tests",
    }
    command = [sys.executable, "-m", "alembic", "-c", "alembic.ini.example"]

    subprocess.run(
        [*command, "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(environment["DATABASE_URL"])

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    try:
        inspector = inspect(engine)

        # Lean column set — exactly the audit contract, nothing more.
        assert {
            column["name"] for column in inspector.get_columns("ai_generations")
        } == {
            "id",
            "action_type",
            "model",
            "template_id",
            "document_id",
            "field_key",
            "created_by",
            "status",
            "suggestions_count",
            "detail",
            "created_at",
        }

        index_names = {
            index["name"] for index in inspector.get_indexes("ai_generations")
        }
        assert index_names == {
            "ix_ai_generations_template_id",
            "ix_ai_generations_created_by",
        }

        # The DDL declares the chosen FK behaviors.
        with engine.connect() as connection:
            ddl = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='ai_generations'"
            ).scalar_one()
        assert "ON DELETE SET NULL" in ddl
        assert "ON DELETE CASCADE" in ddl
        # document_id must NOT reference a documents table (V1.4 arrives later).
        assert "documents" not in ddl

        # Behavior on the migration-created DB: deleting a template SET NULLs.
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO users (email, full_name, role) "
                "VALUES ('migration_owner@example.com', 'Migration Owner', 'normal_user')"
            )
            connection.exec_driver_sql(
                "INSERT INTO templates (name, category, visibility, status, uploaded_by) "
                "VALUES ('Migration Template', 'mom', 'private', 'uploaded', 1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO ai_generations "
                "(action_type, model, template_id, created_by, status) "
                "VALUES ('suggest_fields', 'm', 1, 1, 'success')"
            )
            connection.exec_driver_sql("DELETE FROM templates WHERE id = 1")
            remaining = connection.exec_driver_sql(
                "SELECT template_id, status FROM ai_generations WHERE id = 1"
            ).one()
        assert remaining == (None, "success")
    finally:
        engine.dispose()

    # Target the AI migration's parent; newer migrations can follow it.
    subprocess.run(
        [*command, "downgrade", "b9e5d2c8a740"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(environment["DATABASE_URL"])
    try:
        inspector = inspect(engine)
        assert "ai_generations" not in inspector.get_table_names()
        # Prior migrations' tables are untouched.
        assert "templates" in inspector.get_table_names()
        assert "template_fields" in inspector.get_table_names()
    finally:
        engine.dispose()

    # The chain is re-runnable.
    subprocess.run(
        [*command, "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(environment["DATABASE_URL"])
    try:
        assert "ai_generations" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
