"""
Data-layer tests for the V1.3 Phase 3 field editor.
Member 3 — Database / Integration Developer

Layers:
1. Schema validation: upsert field_name regex / field_type / source rules,
   reorder min-length, sync request shape and defaults.
2. CRUD units: create_field (auto display_order, duplicate rejection),
   update_field (partial, rename collision), delete_field (+reindex
   contiguity), reorder_fields (persistence + permutation guard),
   sync_fields (mixed payload, duplicate/foreign-id rejection, rollback).
3. Type validation: field_type="dropdown" rejected at the ORM layer (the
   schema layer is covered in section 1; the DB CHECK is covered in the
   migration test below).
4. Migration: ck_template_field_type is enforced after upgrade head and
   gone after downgrade -1 (scratch SQLite, alembic via subprocess).
5. API round-trip: edits made through the CRUD layer are reflected, in
   order, by the existing GET /templates/{id}/fields endpoint (Member 2's
   PATCH/PUT/DELETE field endpoints are not shipped yet).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)

from app.crud.template_field_crud import (
    create_field,
    delete_field,
    get_field_by_id,
    get_fields_by_template,
    reorder_fields,
    sync_fields,
    update_field,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.template import Template
from app.models.template_field import TemplateField
from app.models.user import User
from app.schemas.template_field import (
    FieldReorderRequest,
    FieldSyncRequest,
    TemplateFieldCreate,
    TemplateFieldUpdate,
    TemplateFieldUpsert,
)

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


@pytest.fixture()
def db():
    """Function-scoped session for direct CRUD tests (isolated per test)."""
    session = TestSession()
    yield session
    session.rollback()
    session.close()


def _make_template(session, name: str = "Field Editor Test", status: str = "uploaded"):
    template = Template(
        name=name,
        category="mom",
        visibility="private",
        uploaded_by=1,
        status=status,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def _make_field(session, template_id: int, name: str, **overrides):
    return create_field(
        session, template_id, TemplateFieldCreate(field_name=name, **overrides)
    )


# ── 1. Schema validation ──────────────────────────────────────────


def test_upsert_accepts_valid_field():
    item = TemplateFieldUpsert(
        field_name="meeting_title",
        field_label="Meeting Title",
        field_type="textarea",
        is_required=False,
        ai_enabled=True,
    )
    assert item.id is None
    assert item.field_type == "textarea"
    assert item.is_required is False
    assert item.ai_enabled is True


def test_upsert_rejects_invalid_field_name():
    for bad_name in ("Meeting Title", "2date", "camelCase", "has-dash", "has.dot", ""):
        with pytest.raises(Exception):
            TemplateFieldUpsert(field_name=bad_name)


def test_upsert_rejects_invalid_field_type():
    with pytest.raises(Exception):
        TemplateFieldUpsert(field_name="ok_key", field_type="dropdown")


def test_upsert_rejects_invalid_source():
    with pytest.raises(Exception):
        TemplateFieldUpsert(field_name="ok_key", source="guessed")


def test_update_schema_rejects_invalid_field_type():
    with pytest.raises(Exception):
        TemplateFieldUpdate(field_type="dropdown")


def test_update_schema_rejects_invalid_field_name():
    with pytest.raises(Exception):
        TemplateFieldUpdate(field_name="Bad Key")


def test_reorder_request_requires_at_least_one_id():
    with pytest.raises(Exception):
        FieldReorderRequest(ordered_ids=[])


def test_sync_request_defaults():
    request = FieldSyncRequest()
    assert request.fields == []
    assert request.mark_configured is True


# ── 2. CRUD units ─────────────────────────────────────────────────


def test_create_field_assigns_next_display_order(db):
    template = _make_template(db, name="Create Order")
    first = _make_field(db, template.id, "first")
    second = _make_field(db, template.id, "second")
    third = _make_field(db, template.id, "third")

    assert first.display_order == 0
    assert second.display_order == 1
    assert third.display_order == 2


def test_create_field_rejects_duplicate_name(db):
    template = _make_template(db, name="Create Duplicate")
    _make_field(db, template.id, "meeting_title")
    with pytest.raises(ValueError):
        _make_field(db, template.id, "meeting_title")
    assert len(get_fields_by_template(db, template.id)) == 1


def test_get_field_by_id_round_trip(db):
    template = _make_template(db, name="Get By Id")
    created = _make_field(db, template.id, "lookup_key")

    found = get_field_by_id(db, created.id)
    assert found is not None
    assert found.field_name == "lookup_key"
    assert get_field_by_id(db, created.id + 10_000) is None


def test_update_field_changes_only_provided_attrs(db):
    template = _make_template(db, name="Partial Update")
    field = _make_field(
        db,
        template.id,
        "meeting_title",
        field_label="Old Label",
        field_type="text",
        section="Header",
    )

    updated = update_field(db, field, TemplateFieldUpdate(field_label="New Label"))

    assert updated.field_label == "New Label"
    # Untouched attributes keep their values.
    assert updated.field_type == "text"
    assert updated.section == "Header"
    assert updated.is_required is True


def test_update_field_rename_to_existing_key_raises(db):
    template = _make_template(db, name="Rename Collision")
    _make_field(db, template.id, "meeting_title")
    other = _make_field(db, template.id, "meeting_date")

    with pytest.raises(ValueError):
        update_field(db, other, TemplateFieldUpdate(field_name="meeting_title"))
    # The failed rename left the row unchanged.
    fresh = get_field_by_id(db, other.id)
    assert fresh.field_name == "meeting_date"


def test_update_field_rename_to_free_key_succeeds(db):
    template = _make_template(db, name="Rename OK")
    field = _make_field(db, template.id, "old_key")

    updated = update_field(db, field, TemplateFieldUpdate(field_name="new_key"))
    assert updated.field_name == "new_key"


def test_delete_field_reindexes_remaining_fields(db):
    template = _make_template(db, name="Delete Reindex")
    a = _make_field(db, template.id, "alpha")
    b = _make_field(db, template.id, "beta")
    c = _make_field(db, template.id, "gamma")

    delete_field(db, b)

    remaining = get_fields_by_template(db, template.id)
    assert [f.field_name for f in remaining] == ["alpha", "gamma"]
    # Contiguous 0..n-1, no gaps, no duplicates.
    assert [f.display_order for f in remaining] == [0, 1]
    assert get_field_by_id(db, c.id) is not None
    assert get_field_by_id(db, a.id) is not None


def test_reorder_fields_persists_new_order(db):
    template = _make_template(db, name="Reorder OK")
    a = _make_field(db, template.id, "alpha")
    b = _make_field(db, template.id, "beta")
    c = _make_field(db, template.id, "gamma")

    result = reorder_fields(db, template.id, [c.id, a.id, b.id])

    assert [f.field_name for f in result] == ["gamma", "alpha", "beta"]
    assert [f.display_order for f in result] == [0, 1, 2]


def test_reorder_fields_rejects_non_permutation(db):
    template = _make_template(db, name="Reorder Bad")
    a = _make_field(db, template.id, "alpha")
    b = _make_field(db, template.id, "beta")
    c = _make_field(db, template.id, "gamma")

    # Missing id.
    with pytest.raises(ValueError):
        reorder_fields(db, template.id, [a.id, b.id])
    # Extra (unknown) id.
    with pytest.raises(ValueError):
        reorder_fields(db, template.id, [a.id, b.id, c.id, 999])
    # Duplicated id.
    with pytest.raises(ValueError):
        reorder_fields(db, template.id, [a.id, a.id, c.id])
    # Nothing changed on failure.
    assert [f.display_order for f in get_fields_by_template(db, template.id)] == [
        0,
        1,
        2,
    ]


def test_sync_fields_mixed_payload(db):
    """2 existing updated, 1 new created, 1 existing omitted -> deleted."""
    template = _make_template(db, name="Sync Mixed")
    a = _make_field(db, template.id, "alpha", field_label="Alpha Label")
    b = _make_field(db, template.id, "beta")
    _make_field(db, template.id, "gamma")  # omitted -> deleted

    result = sync_fields(
        db,
        template.id,
        [
            # Update: display_order=99 must be ignored (array index wins).
            TemplateFieldUpsert(
                id=b.id,
                field_name="beta",
                field_label="Beta Edited",
                display_order=99,
            ),
            # Create: defaults filled, source -> manual.
            TemplateFieldUpsert(
                field_name="delta", field_type="number", is_required=False
            ),
            # Update: rename.
            TemplateFieldUpsert(id=a.id, field_name="alpha_renamed"),
        ],
    )

    assert [f.field_name for f in result] == ["beta", "delta", "alpha_renamed"]
    assert [f.display_order for f in result] == [0, 1, 2]

    assert result[0].field_label == "Beta Edited"
    assert result[0].is_required is True  # not sent -> kept

    assert result[1].field_type == "number"
    assert result[1].is_required is False
    assert result[1].source == "manual"

    assert result[2].field_label == "Alpha Label"  # rename applied, label kept

    # gamma was absent from the payload -> deleted. (Do not assert on c.id:
    # SQLite may reuse the freed rowid for the newly created row.)
    remaining = get_fields_by_template(db, template.id)
    assert "gamma" not in [f.field_name for f in remaining]
    assert len(remaining) == 3


def test_sync_fields_empty_payload_clears_all(db):
    template = _make_template(db, name="Sync Clear")
    _make_field(db, template.id, "alpha")
    _make_field(db, template.id, "beta")

    result = sync_fields(db, template.id, [])
    assert result == []
    assert get_fields_by_template(db, template.id) == []


def test_sync_fields_rejects_duplicate_name_in_payload(db):
    template = _make_template(db, name="Sync Duplicate")
    existing = _make_field(db, template.id, "alpha")

    with pytest.raises(ValueError):
        sync_fields(
            db,
            template.id,
            [
                TemplateFieldUpsert(id=existing.id, field_name="dupe"),
                TemplateFieldUpsert(field_name="dupe"),
            ],
        )
    # No partial writes: original state preserved.
    fields = get_fields_by_template(db, template.id)
    assert [f.field_name for f in fields] == ["alpha"]


def test_sync_fields_rejects_id_from_another_template(db):
    home = _make_template(db, name="Sync Home")
    foreign = _make_template(db, name="Sync Foreign")
    home_field = _make_field(db, home.id, "home_key")
    foreign_field = _make_field(db, foreign.id, "foreign_key")

    with pytest.raises(ValueError):
        sync_fields(
            db,
            home.id,
            [
                TemplateFieldUpsert(id=home_field.id, field_name="home_key"),
                TemplateFieldUpsert(id=foreign_field.id, field_name="foreign_key"),
            ],
        )
    # Both templates untouched.
    assert [f.field_name for f in get_fields_by_template(db, home.id)] == ["home_key"]
    assert [f.field_name for f in get_fields_by_template(db, foreign.id)] == [
        "foreign_key",
    ]


def test_sync_fields_rolls_back_on_integrity_error(db):
    """A cross-item rename collision fails at commit: nothing is written."""
    template = _make_template(db, name="Sync Rollback")
    x = _make_field(db, template.id, "x")
    y = _make_field(db, template.id, "y")

    # Renaming x -> y collides with y (y is kept, renamed to z in the same
    # flush) -> IntegrityError -> full rollback.
    with pytest.raises(IntegrityError):
        sync_fields(
            db,
            template.id,
            [
                TemplateFieldUpsert(id=x.id, field_name="y"),
                TemplateFieldUpsert(id=y.id, field_name="z"),
            ],
        )

    fields = get_fields_by_template(db, template.id)
    assert [f.field_name for f in fields] == ["x", "y"]
    assert [f.display_order for f in fields] == [0, 1]
    assert get_field_by_id(db, x.id) is not None
    assert get_field_by_id(db, y.id) is not None


# ── 3. ORM-level type validation ──────────────────────────────────


def test_orm_rejects_invalid_field_type():
    with pytest.raises(ValueError):
        TemplateField(template_id=1, field_name="bad_type", field_type="dropdown")


# ── 4. Migration: ck_template_field_check enforced + reversible ────


def test_field_type_check_constraint_enforced_and_reversible(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    database_path = (tmp_path / "field-type-check.db").as_posix()
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
    try:
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO template_fields "
                        "(template_id, field_name, field_type) "
                        "VALUES (1, 'bad_type', 'dropdown')"
                    )
                )
        # The valid vocabulary still inserts fine.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO template_fields "
                    "(template_id, field_name, field_type) "
                    "VALUES (1, 'ok_type', 'signature')"
                )
            )
    finally:
        engine.dispose()

    # Downgrade past the b9e5d2c8a740 check-constraint revision (to its
    # parent 3f8d2c6a9e41). "downgrade -1" no longer targets it now that
    # later migrations (Phase 4's ai_generations) chain on top of it.
    subprocess.run(
        [*command, "downgrade", "3f8d2c6a9e41"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(environment["DATABASE_URL"])
    try:
        # Constraint gone: the previously rejected type now inserts.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO template_fields "
                    "(template_id, field_name, field_type) "
                    "VALUES (1, 'ok_after_downgrade', 'dropdown')"
                )
            )
    finally:
        engine.dispose()


# ── 5. API round-trip through the existing GET /fields endpoint ───


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
def field_owner_token():
    return _signup_and_login("field_editor@example.com", "Field Editor")


def test_fields_endpoint_reflects_edits_in_order(field_owner_token):
    with TestSession() as session:
        user = session.execute(
            select(User).where(User.email == "field_editor@example.com")
        ).scalar_one()
        template = Template(
            name="Editor Round Trip",
            category="mom",
            visibility="private",
            uploaded_by=user.id,
            status="placeholder_detected",
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        template_id = template.id

        f1 = _make_field(session, template_id, "meeting_title", field_label="Title")
        f2 = _make_field(session, template_id, "meeting_date", field_type="date")
        f3 = _make_field(session, template_id, "attendees", field_type="list")
        f1_id, f2_id = f1.id, f2.id

        update_field(
            session,
            f2,
            TemplateFieldUpdate(field_label="Meeting Date", is_required=False),
        )
        delete_field(session, f3)
        reorder_fields(session, template_id, [f2_id, f1_id])

    response = client.get(
        f"/api/v1/templates/{template_id}/fields",
        headers={"Authorization": f"Bearer {field_owner_token}"},
    )
    assert response.status_code == 200, response.json()
    body = response.json()

    assert [f["field_name"] for f in body] == ["meeting_date", "meeting_title"]
    assert [f["display_order"] for f in body] == [0, 1]
    assert body[0]["field_label"] == "Meeting Date"
    assert body[0]["is_required"] is False
    assert body[0]["field_type"] == "date"
