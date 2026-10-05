"""
V1.4 Phase 2 - Document Schemas

Pydantic schemas for document persistence (draft save functionality).
These schemas will be used by Member 2 in Phase 2 when building:
- POST /documents/create
- PUT /documents/{id}/values
- GET /documents
- GET /documents/{id}
- GET /documents/{id}/values

Phase 1: These are DRAFT schemas (not yet wired to endpoints).
Phase 2: Member 2 will use these for endpoints, Member 3 will create the tables.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Document Schemas ---


class DocumentCreate(BaseModel):
    """
    Payload for POST /documents/create.

    Creates a new document draft based on a template.
    Initial status is always 'draft'.
    """

    template_id: int = Field(..., description="ID of the template to create document from")
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional user-given name (auto-generated if null)",
    )


class DocumentUpdate(BaseModel):
    """
    Payload for PATCH /documents/{id}.

    Updates document metadata (name, status).
    All fields are optional for partial updates.
    """

    name: str | None = Field(default=None, max_length=255)
    status: str | None = Field(
        default=None,
        description=(
            "Status: draft, generated, submitted, approved, rejected, final. "
            "Phase 2 only uses 'draft' and 'generated'."
        ),
    )


class DocumentRead(BaseModel):
    """
    Response for GET /documents or GET /documents/{id}.

    Includes document metadata and optionally joined values.
    """

    id: int
    template_id: int
    created_by: int
    name: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    # Optional: eagerly loaded values (when include_values=true)
    values: list["DocumentValueRead"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# --- DocumentValue Schemas ---


class DocumentValueCreate(BaseModel):
    """
    Payload for one field value in PUT /documents/{id}/values.

    The endpoint accepts a list of these for bulk upsert.
    """

    field_name: str = Field(
        ...,
        max_length=100,
        description="Must match template_fields.field_name",
    )
    value: str = Field(
        ...,
        description=(
            "Value as string. For list fields, use JSON array string "
            "(e.g., '[\"item1\", \"item2\"]'). For date, use ISO format "
            "(e.g., '2026-09-13'). For number, use string representation (e.g., '42')."
        ),
    )


class DocumentValueUpdate(BaseModel):
    """
    Payload for updating a single document value (future use).

    Phase 2 uses bulk upsert via DocumentValueCreate list.
    This schema is for potential future single-field update endpoint.
    """

    value: str = Field(..., description="New value as string")


class DocumentValueRead(BaseModel):
    """
    Response for document values in GET /documents/{id}/values or nested in DocumentRead.

    Returns the persisted value with metadata.
    """

    id: int
    document_id: int
    field_name: str
    value: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Bulk Operations ---


class DocumentValuesBulkUpsert(BaseModel):
    """
    Payload for PUT /documents/{id}/values (Phase 2).

    Accepts a list of field values for bulk upsert.
    Upsert behavior:
    - If (document_id, field_name) exists, update value + updated_at
    - If not, insert new row
    """

    values: list[DocumentValueCreate] = Field(
        ...,
        description="List of field values to upsert",
        min_length=1,
    )


class DocumentValuesBulkRead(BaseModel):
    """
    Response for GET /documents/{id}/values (Phase 2).

    Returns all values for a document, optionally ordered by display_order
    (requires join with template_fields).
    """

    document_id: int
    values: list[DocumentValueRead]


# --- Validation Error Schemas (Phase 2) ---


class FieldValidationError(BaseModel):
    """
    One field validation error in the bulk validation response.

    Returned when a field value fails validation_rule checks.
    """

    field_name: str
    field_label: str
    message: str
    rule: str  # e.g., "email", "min:5", "max:100", "regex:^[A-Z]+$"


class DocumentValidationErrorResponse(BaseModel):
    """
    HTTP 422 response when document_values validation fails (Phase 2).

    Contains structured list of field-level errors.
    """

    detail: list[FieldValidationError]


# --- Summary/List Schemas ---


class DocumentListItem(BaseModel):
    """
    Lightweight document item for GET /documents list view (Phase 2).

    Does not include values (use DocumentRead with include_values for that).
    """

    id: int
    template_id: int
    template_name: str  # Joined from templates.name
    name: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Phase 2 Integration Notes ---

"""
Phase 2 Endpoint Mapping:

POST /documents/create
  Request: DocumentCreate
  Response: DocumentRead (empty values list)

PUT /documents/{id}/values
  Request: DocumentValuesBulkUpsert
  Response: DocumentValuesBulkRead
  Error: DocumentValidationErrorResponse (HTTP 422)

GET /documents
  Response: list[DocumentListItem] (user's drafts, ordered by updated_at desc)

GET /documents/{id}
  Response: DocumentRead (with values if include_values=true)

GET /documents/{id}/values
  Response: DocumentValuesBulkRead

PATCH /documents/{id}
  Request: DocumentUpdate
  Response: DocumentRead

DELETE /documents/{id}
  Response: {"ok": true} (cascade deletes values via FK)

---

Member 3 (Phase 2) will create:
- documents table with columns matching DocumentRead
- document_values table with columns matching DocumentValueRead
- Relationships: documents -> template, documents -> user, document_values -> documents (CASCADE)

Member 2 (Phase 2) will:
- Implement endpoints using these schemas
- Enforce validation_rule checks server-side (see backend/docs/validation-rules.md)
- Return structured errors (FieldValidationError list) on validation failure
"""
