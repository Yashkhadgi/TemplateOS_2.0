from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TemplateBase(BaseModel):
    name: str
    description: str | None = None
    category: str
    visibility: str


class TemplateCreate(TemplateBase):
    original_file_path: str | None = None
    original_filename: str | None = None
    file_size_bytes: int | None = None
    file_extension: str | None = None
    uploaded_by: int


class TemplateResponse(TemplateBase):
    id: int
    status: str
    original_file_path: str | None = None
    processed_file_path: str | None = (
        None  # V1.3 Phase 2: cleaned copy (renderable source)
    )
    original_filename: str | None = None
    file_size_bytes: int | None = None
    uploaded_by: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateListItem(BaseModel):
    id: int
    name: str
    category: str
    visibility: str
    status: str
    uploaded_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateLibraryResponse(BaseModel):
    templates: list[TemplateListItem]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)
