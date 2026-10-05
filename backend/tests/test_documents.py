"""
Model + CRUD + Integration tests for documents and document_values.
V1.4 Phase 2 — Member 3
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure we're using a dummy DB and secret (inline-SQLite pattern)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)
# Override Git Bash's bogus API_V1_PREFIX
os.environ["API_V1_PREFIX"] = "/api/v1"

from app.crud.document_crud import (
    create_document,
    delete_document,
    get_document_by_id,
    get_documents_by_user,
    update_document_status,
)
from app.crud.document_value_crud import (
    delete_values_by_document,
    get_values_by_document,
    upsert_values,
)
from app.db.base import Base
from app.models.document import DOCUMENT_STATUSES, Document
from app.models.document_value import DocumentValue
from app.models.template import Template
from app.models.user import User  # noqa: F401 — registers the users table in metadata

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


def _make_user(session, email: str = "test@example.com") -> User:
    user = User(
        email=email,
        full_name="Test User",
        role="normal_user",
        hashed_password="hashed",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_template(session, user_id: int, name: str = "Test Template") -> Template:
    template = Template(
        name=name,
        category="notice",
        visibility="private",
        uploaded_by=user_id,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


# ── Model Tests ──────────────────────────────────────────────────────────


def test_document_defaults_on_instantiation(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = Document(template_id=template.id, created_by=user.id)
    assert doc.status == "draft"
    assert doc.name is None


def test_document_invalid_status_raises(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = Document(template_id=template.id, created_by=user.id)
    with pytest.raises(ValueError):
        doc.status = "invalid_xyz"


def test_document_valid_statuses_accepted(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    for status in DOCUMENT_STATUSES:
        doc = Document(template_id=template.id, created_by=user.id, status=status)
        assert doc.status == status


def test_document_value_unique_constraint(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = Document(template_id=template.id, created_by=user.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    db.add(DocumentValue(document_id=doc.id, field_name="employee_name", value="John"))
    db.commit()

    # Duplicate field_name for same document should raise
    db.add(DocumentValue(document_id=doc.id, field_name="employee_name", value="Jane"))
    with pytest.raises(IntegrityError):
        db.commit()


# ── CRUD Tests ───────────────────────────────────────────────────────────


def test_create_document_sets_defaults(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    assert doc.id is not None
    assert doc.template_id == template.id
    assert doc.created_by == user.id
    assert doc.status == "draft"
    assert doc.name is None


def test_create_document_with_name_and_status(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id, name="My Draft", status="draft")
    assert doc.name == "My Draft"
    assert doc.status == "draft"


def test_create_document_invalid_status_raises(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    with pytest.raises(ValueError):
        create_document(db, template.id, user.id, status="invalid_xyz")


def test_get_document_by_id(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    fetched = get_document_by_id(db, doc.id)
    assert fetched is not None
    assert fetched.id == doc.id


def test_get_document_by_id_not_found(db):
    result = get_document_by_id(db, 9999)
    assert result is None


def test_get_document_by_id_with_values(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    upsert_values(db, doc.id, [{"field_name": "field1", "value": "val1"}])

    fetched = get_document_by_id(db, doc.id, include_values=True)
    assert fetched is not None
    assert len(fetched.values) == 1
    assert fetched.values[0].field_name == "field1"
    assert fetched.values[0].value == "val1"


def test_get_documents_by_user_ordered_by_updated_at(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc1 = create_document(db, template.id, user.id, name="First")
    doc2 = create_document(db, template.id, user.id, name="Second")

    # Touch doc1 to make it more recent
    doc1.name = "First Updated"
    db.commit()

    docs = get_documents_by_user(db, user.id)
    assert len(docs) == 2
    assert docs[0].id == doc1.id  # Most recent first
    assert docs[1].id == doc2.id


def test_get_documents_by_user_scoped(db):
    user1 = _make_user(db, "user1@example.com")
    user2 = _make_user(db, "user2@example.com")
    template = _make_template(db, user1.id)
    create_document(db, template.id, user1.id)
    create_document(db, template.id, user2.id)

    assert len(get_documents_by_user(db, user1.id)) == 1
    assert len(get_documents_by_user(db, user2.id)) == 1


def test_update_document_status(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    updated = update_document_status(db, doc.id, "generated")
    assert updated is not None
    assert updated.status == "generated"


def test_update_document_status_invalid_raises(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    with pytest.raises(ValueError):
        update_document_status(db, doc.id, "invalid_xyz")


def test_update_document_status_not_found(db):
    result = update_document_status(db, 9999, "draft")
    assert result is None


def test_delete_document_cascades_values(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    upsert_values(db, doc.id, [{"field_name": "field1", "value": "val1"}])

    assert get_document_by_id(db, doc.id) is not None
    assert len(get_values_by_document(db, doc.id)) == 1

    deleted = delete_document(db, doc.id)
    assert deleted is True

    assert get_document_by_id(db, doc.id) is None
    assert get_values_by_document(db, doc.id) == []


def test_delete_document_not_found(db):
    result = delete_document(db, 9999)
    assert result is False


def test_upsert_values_insert_and_update(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)

    # Insert
    rows = upsert_values(db, doc.id, [{"field_name": "field1", "value": "val1"}])
    assert len(rows) == 1
    assert rows[0].field_name == "field1"
    assert rows[0].value == "val1"

    # Update same field
    rows = upsert_values(
        db, doc.id, [{"field_name": "field1", "value": "val1_updated"}]
    )
    assert len(rows) == 1
    assert rows[0].value == "val1_updated"

    # Verify only one row exists
    all_values = get_values_by_document(db, doc.id)
    assert len(all_values) == 1
    assert all_values[0].value == "val1_updated"


def test_upsert_values_multiple_fields(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)

    rows = upsert_values(
        db,
        doc.id,
        [
            {"field_name": "field1", "value": "val1"},
            {"field_name": "field2", "value": "val2"},
            {"field_name": "field3", "value": "val3"},
        ],
    )
    assert len(rows) == 3
    all_values = get_values_by_document(db, doc.id)
    assert len(all_values) == 3
    assert {v.field_name for v in all_values} == {"field1", "field2", "field3"}


def test_upsert_values_mixed_insert_and_update(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)

    # First batch
    upsert_values(db, doc.id, [{"field_name": "field1", "value": "val1"}])
    # Second batch: update field1, insert field2
    upsert_values(
        db,
        doc.id,
        [
            {"field_name": "field1", "value": "val1_updated"},
            {"field_name": "field2", "value": "val2"},
        ],
    )

    all_values = get_values_by_document(db, doc.id)
    assert len(all_values) == 2
    by_name = {v.field_name: v.value for v in all_values}
    assert by_name["field1"] == "val1_updated"
    assert by_name["field2"] == "val2"


def test_get_values_by_document(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    upsert_values(db, doc.id, [{"field_name": "field1", "value": "val1"}])

    values = get_values_by_document(db, doc.id)
    assert len(values) == 1
    assert values[0].field_name == "field1"
    assert values[0].value == "val1"


def test_delete_values_by_document(db):
    user = _make_user(db)
    template = _make_template(db, user.id)
    doc = create_document(db, template.id, user.id)
    upsert_values(db, doc.id, [{"field_name": "field1", "value": "val1"}])

    deleted = delete_values_by_document(db, doc.id)
    assert deleted == 1
    assert get_values_by_document(db, doc.id) == []
