from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.template import Template
    from app.models.document import Document

USER_ROLES = (
    "super_admin",
    "org_admin",
    "department_admin",
    "faculty",
    "student",
    "approver",
    "normal_user",
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="normal_user")
    # Nullable only to keep the migration safe for any users created before auth existed.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    signature_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    @validates("role")
    def validate_role(self, _key: str, role: str) -> str:
        if role not in USER_ROLES:
            raise ValueError(f"Unsupported user role: {role}")
        return role

    templates: Mapped[list["Template"]] = relationship(
        "Template", back_populates="uploader"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="creator"
    )
