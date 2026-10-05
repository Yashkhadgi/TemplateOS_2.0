"""
Model + CRUD tests for the expanded template_fields metadata.
V1.3 Phase 1 — Member 3
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure we're using a dummy DB and secret (keeps the inline-SQLite pattern
# used by the other test modules).
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)

from app.crud.template_field_crud import (
    bulk_create_fields,
    delete_fields_by_template,
    field_exists,
    get_fields_by_template,
)
from app.db.base import Base
from app.models.template import Template
from app.models.template_field import FIELD_TYPES, TemplateField
from app.models.user import User  # noqa: F401 — registers the users table in metadata
from app.schemas.template_field import TemplateFieldCreate

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def _make_template(session, name: str = "Notice Template") -> Template:
    template = Template(
        name=name,
        category="notice",
        visibility="private",
        uploaded_by=1,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


# ── Model ──────────────────────────────────────────────────────────


def test_field_defaults_on_instantiation():
    field = TemplateField(template_id=1, field_name="employee_name")
    assert field.field_type == "text"
    assert field.is_required is True
    assert field.display_order == 0
    assert field.ai_enabled is False
    assert field.field_label is None
    assert field.section is None
    assert field.example_value is None
    assert field.validation_rule is None
    assert field.description is None


def test_field_types_vocabulary_is_mvp_set():
    assert FIELD_TYPES == ("text", "textarea", "date", "number", "list", "signature")


def test_field_accepts_textarea_and_list():
    assert (
        TemplateField(template_id=1, field_name="a", field_type="textarea").field_type
        == "textarea"
    )
    assert (
        TemplateField(template_id=1, field_name="b", field_type="list").field_type
        == "list"
    )


def test_field_rejects_dropdown():
    with pytest.raises(ValueError):
        TemplateField(template_id=1, field_name="c", field_type="dropdown")


def test_field_rejects_unknown_type():
    with pytest.raises(ValueError):
        TemplateField(template_id=1, field_name="d", field_type="hologram")


def test_unique_template_field_key(db):
    template = _make_template(db)
    db.add(TemplateField(template_id=template.id, field_name="employee_name"))
    db.commit()
    db.add(TemplateField(template_id=template.id, field_name="employee_name"))
    with pytest.raises(IntegrityError):
        db.commit()


# ── CRUD ───────────────────────────────────────────────────────────


def test_bulk_create_preserves_order_and_assigns_template(db):
    template = _make_template(db)
    rows = bulk_create_fields(
        db,
        template.id,
        [
            TemplateFieldCreate(
                field_name="employee_name", field_label="Employee Name", display_order=0
            ),
            TemplateFieldCreate(
                field_name="start_date", field_type="date", display_order=1
            ),
            TemplateFieldCreate(
                field_name="summary", field_type="textarea", display_order=2
            ),
        ],
    )
    assert [r.field_name for r in rows] == ["employee_name", "start_date", "summary"]
    assert all(r.template_id == template.id for r in rows)
    assert all(r.id is not None for r in rows)


def test_bulk_create_persists_full_metadata(db):
    template = _make_template(db)
    rows = bulk_create_fields(
        db,
        template.id,
        [
            TemplateFieldCreate(
                field_name="salary",
                field_label="Monthly Salary",
                field_type="number",
                is_required=False,
                description="Gross monthly salary",
                section="Compensation",
                example_value="50000",
                validation_rule="min:0",
                ai_enabled=True,
                display_order=3,
            ),
        ],
    )
    row = rows[0]
    assert row.field_label == "Monthly Salary"
    assert row.field_type == "number"
    assert row.is_required is False
    assert row.description == "Gross monthly salary"
    assert row.section == "Compensation"
    assert row.example_value == "50000"
    assert row.validation_rule == "min:0"
    assert row.ai_enabled is True
    assert row.display_order == 3


def test_bulk_create_with_empty_list_is_noop(db):
    template = _make_template(db)
    assert bulk_create_fields(db, template.id, []) == []
    assert get_fields_by_template(db, template.id) == []


def test_bulk_create_rejects_duplicate_keys(db):
    template = _make_template(db)
    with pytest.raises(IntegrityError):
        bulk_create_fields(
            db,
            template.id,
            [
                TemplateFieldCreate(field_name="employee_name"),
                TemplateFieldCreate(field_name="employee_name"),
            ],
        )


def test_get_fields_by_template_orders_by_display_order(db):
    template = _make_template(db)
    bulk_create_fields(
        db,
        template.id,
        [
            TemplateFieldCreate(field_name="c_third", display_order=2),
            TemplateFieldCreate(field_name="a_first", display_order=0),
            TemplateFieldCreate(field_name="b_second", display_order=1),
        ],
    )
    fields = get_fields_by_template(db, template.id)
    assert [f.field_name for f in fields] == ["a_first", "b_second", "c_third"]


def test_get_fields_tie_breaks_by_id(db):
    template = _make_template(db)
    bulk_create_fields(
        db,
        template.id,
        [
            TemplateFieldCreate(field_name="first_inserted", display_order=0),
            TemplateFieldCreate(field_name="second_inserted", display_order=0),
        ],
    )
    fields = get_fields_by_template(db, template.id)
    assert [f.field_name for f in fields] == ["first_inserted", "second_inserted"]


def test_get_fields_scoped_to_template(db):
    template = _make_template(db)
    other = _make_template(db, name="Other Template")
    bulk_create_fields(db, template.id, [TemplateFieldCreate(field_name="mine")])
    bulk_create_fields(db, other.id, [TemplateFieldCreate(field_name="theirs")])
    assert [f.field_name for f in get_fields_by_template(db, template.id)] == ["mine"]


def test_delete_fields_by_template_clears_only_target(db):
    template = _make_template(db)
    other = _make_template(db, name="Other Template")
    bulk_create_fields(db, template.id, [TemplateFieldCreate(field_name="x")])
    bulk_create_fields(db, other.id, [TemplateFieldCreate(field_name="y")])

    deleted = delete_fields_by_template(db, template.id)

    assert deleted == 1
    assert get_fields_by_template(db, template.id) == []
    assert [f.field_name for f in get_fields_by_template(db, other.id)] == ["y"]


def test_delete_fields_by_template_returns_zero_when_empty(db):
    template = _make_template(db)
    assert delete_fields_by_template(db, template.id) == 0


def test_field_exists(db):
    template = _make_template(db)
    bulk_create_fields(
        db, template.id, [TemplateFieldCreate(field_name="employee_name")]
    )
    assert field_exists(db, template.id, "employee_name") is True
    assert field_exists(db, template.id, "missing_key") is False
    assert field_exists(db, template.id + 999, "employee_name") is False
