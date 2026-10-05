"""
Template cleaning request/response schemas (V1.3 Phase 2 — Member 3).

Manual Template Cleaning lets an owner convert selected sample text in the
original DOCX into {{placeholders}}, producing a processed DOCX (Member 2's
docx_cleaner) while preserving the original. These are the data contracts
Member 2's GET /{id}/content + POST /{id}/clean endpoints consume/return and
Member 1's UI mirrors.
"""

import re

from pydantic import BaseModel, Field, field_validator

from app.models.template_field import FIELD_TYPES
from app.schemas.template_field import TemplateFieldRead

# Same rule as Phase 1's VALID_KEY_PATTERN (app/services/docx_parser.py).
PLACEHOLDER_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class PlaceholderReplacement(BaseModel):
    """One confirmed sample-text -> placeholder conversion from the owner."""

    sample_text: str = Field(
        ..., min_length=1, description="The exact text the owner selected"
    )
    placeholder_key: str = Field(
        ..., description="Target placeholder key, lowercase snake_case"
    )
    field_label: str | None = Field(default=None, max_length=150)
    field_type: str | None = Field(
        default=None, description=f"One of {FIELD_TYPES} if provided"
    )
    section: str | None = Field(default=None, max_length=100)
    segment_index: int | None = Field(
        default=None,
        description="Optional scope hint (TextSegment.index) from the UI",
    )

    @field_validator("placeholder_key")
    @classmethod
    def validate_placeholder_key(cls, value: str) -> str:
        if not PLACEHOLDER_KEY_PATTERN.match(value):
            raise ValueError(
                "placeholder_key must be lowercase snake_case "
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


class CleanTemplateRequest(BaseModel):
    """Owner-confirmed batch of replacements to apply to the original DOCX."""

    replacements: list[PlaceholderReplacement] = Field(..., min_length=1)
    confirm: bool = Field(
        default=False,
        description="Must be true — cleaning is a manual-confirmation action",
    )
    mark_configured: bool = Field(
        default=False,
        description="If true, status advances to field_configured; else placeholder_detected",
    )


class ReplacementResult(BaseModel):
    """Per-replacement outcome, echoed to the UI."""

    placeholder_key: str
    sample_text: str
    occurrences: int = 0
    matched: bool = False
    reason: str | None = None


class CleanWarnings(BaseModel):
    unmatched: list[str] = Field(
        default_factory=list, description="Sample texts not found in the document"
    )
    invalid_keys: list[str] = Field(
        default_factory=list, description="Keys rejected by validation"
    )


class CleanTemplateResponse(BaseModel):
    template_id: int
    status: str
    processed_file_path: str
    created_fields: list[TemplateFieldRead] = Field(default_factory=list)
    results: list[ReplacementResult] = Field(default_factory=list)
    warnings: CleanWarnings
