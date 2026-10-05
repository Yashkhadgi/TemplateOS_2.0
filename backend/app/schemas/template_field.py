import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.template_field import FIELD_SOURCES, FIELD_TYPES

# Same rule as Phase 1's VALID_KEY_PATTERN (app/services/docx_parser.py)
# and Phase 2's PLACEHOLDER_KEY_PATTERN (app/schemas/cleaning.py).
_FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class TemplateFieldBase(BaseModel):
    field_name: str = Field(..., max_length=100)
    field_label: str | None = Field(default=None, max_length=150)
    field_type: str = Field(default="text", max_length=20)
    default_value: str | None = Field(default=None, max_length=255)
    is_required: bool = Field(default=True)
    description: str | None = Field(default=None)
    section: str | None = Field(default=None, max_length=100)
    example_value: str | None = Field(default=None, max_length=255)
    validation_rule: str | None = Field(default=None, max_length=255)
    ai_enabled: bool = Field(default=False)
    display_order: int = Field(default=0)
    source: str = Field(default="detected", max_length=20)

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, value: str) -> str:
        if value not in FIELD_TYPES:
            raise ValueError(
                f"Unsupported field type: {value}. Allowed: {', '.join(FIELD_TYPES)}"
            )
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if value not in FIELD_SOURCES:
            raise ValueError(
                f"Unsupported field source: {value}. Allowed: {', '.join(FIELD_SOURCES)}"
            )
        return value


class TemplateFieldCreate(TemplateFieldBase):
    """Payload used by detection/cleaning to create fields (template_id comes from the CRUD layer)."""

    pass


class TemplateFieldUpdate(BaseModel):
    """Partial update payload for the Phase 3 field editor."""

    field_name: str | None = Field(None, max_length=100)
    field_label: str | None = Field(None, max_length=150)
    field_type: str | None = Field(None, max_length=20)
    default_value: str | None = Field(None, max_length=255)
    is_required: bool | None = None
    description: str | None = None
    section: str | None = Field(None, max_length=100)
    example_value: str | None = Field(None, max_length=255)
    validation_rule: str | None = Field(None, max_length=255)
    ai_enabled: bool | None = None
    display_order: int | None = None
    source: str | None = Field(None, max_length=20)

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str | None) -> str | None:
        if value is not None and not _FIELD_NAME_PATTERN.match(value):
            raise ValueError(
                "field_name must be lowercase snake_case "
                "(letters, digits, underscores) and start with a letter"
            )
        return value

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, value: str | None) -> str | None:
        if value is not None and value not in FIELD_TYPES:
            raise ValueError(
                f"Unsupported field type: {value}. Allowed: {', '.join(FIELD_TYPES)}"
            )
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is not None and value not in FIELD_SOURCES:
            raise ValueError(
                f"Unsupported field source: {value}. Allowed: {', '.join(FIELD_SOURCES)}"
            )
        return value


class TemplateFieldRead(TemplateFieldBase):
    id: int
    template_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- V1.3 Phase 3 field editor (upsert / reorder / sync) ---
# Member 2 wires these into POST/PATCH/DELETE/PUT field endpoints.


class TemplateFieldUpsert(BaseModel):
    """
    One field in a Phase 3 editor save.

    id present  -> update that field (only sent attributes are applied)
    id absent   -> create a new field

    display_order is NOT trusted from the client in sync payloads (array
    position wins); it stays optional for single-create payloads.
    """

    id: int | None = None
    field_name: str = Field(..., max_length=100)
    field_label: str | None = Field(default=None, max_length=150)
    field_type: str | None = Field(
        default=None, max_length=20, description=f"One of {FIELD_TYPES} if provided"
    )
    default_value: str | None = Field(default=None, max_length=255)
    is_required: bool = Field(default=True)
    description: str | None = Field(default=None)
    section: str | None = Field(default=None, max_length=100)
    example_value: str | None = Field(default=None, max_length=255)
    validation_rule: str | None = Field(default=None, max_length=255)
    ai_enabled: bool = Field(default=False)
    display_order: int | None = Field(
        default=None,
        description="Only honored on single create; sync uses array position",
    )
    source: str | None = Field(
        default=None,
        max_length=20,
        description=f"One of {FIELD_SOURCES} if provided; defaults to 'manual' on create",
    )

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        if not _FIELD_NAME_PATTERN.match(value):
            raise ValueError(
                "field_name must be lowercase snake_case "
                "(letters, digits, underscores) and start with a letter"
            )
        return value

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, value: str | None) -> str | None:
        if value is not None and value not in FIELD_TYPES:
            raise ValueError(
                f"Unsupported field type: {value}. Allowed: {', '.join(FIELD_TYPES)}"
            )
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is not None and value not in FIELD_SOURCES:
            raise ValueError(
                f"Unsupported field source: {value}. Allowed: {', '.join(FIELD_SOURCES)}"
            )
        return value


class FieldReorderRequest(BaseModel):
    """Explicit reorder payload: the full, exact id sequence in the new order."""

    ordered_ids: list[int] = Field(..., min_length=1)


class FieldSyncRequest(BaseModel):
    """
    Full-sync save from the field editor.

    `fields` is the complete desired state: items with an id update, items
    without an id create, and existing fields absent from the list are
    deleted. An empty list clears every field (Member 2 gates
    mark_configured on >=1 field).
    """

    fields: list[TemplateFieldUpsert] = Field(default_factory=list)
    mark_configured: bool = Field(
        default=True,
        description="If true, status advances to field_configured after the sync",
    )


# --- V1.3 Phase 1 placeholder detection response ---
# Mirrors Member 2's DetectionResult (app/services/docx_parser.py) and the
# Member 1 frontend types (frontend/src/lib/api.ts).


class DuplicateFieldWarning(BaseModel):
    """A valid key that appears more than once; collapsed into one field."""

    key: str
    count: int


class InvalidFieldNameWarning(BaseModel):
    """A malformed token like {{Bad Name}}; reported, never persisted."""

    raw: str
    suggested_key: str
    count: int
    reason: str


class DetectionWarnings(BaseModel):
    duplicates: list[DuplicateFieldWarning] = Field(default_factory=list)
    invalid_names: list[InvalidFieldNameWarning] = Field(default_factory=list)
    parse_error: str | None = None


class DetectionSummary(BaseModel):
    total_matches: int
    unique_valid: int
    invalid_count: int
    duplicate_count: int


class PlaceholderDetectionResponse(BaseModel):
    template_id: int
    status: str
    already_detected: bool
    detected_fields: list[TemplateFieldRead] = Field(default_factory=list)
    warnings: DetectionWarnings
    summary: DetectionSummary
