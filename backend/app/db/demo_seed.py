from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import USER_ROLES, User


@dataclass(frozen=True)
class DemoUserDefinition:
    environment_prefix: str
    full_name: str
    role: str
    department: str | None
    organization: str
    job_title: str | None


@dataclass(frozen=True)
class DemoUserSeed:
    email: str
    password: str
    full_name: str
    role: str
    department: str | None = None
    organization: str | None = None
    job_title: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    signature_path: str | None = None
    preferences: dict[str, Any] | None = None


DEMO_USER_DEFINITIONS = (
    DemoUserDefinition(
        "SIT_SUPER_ADMIN",
        "Demo Super Admin",
        "super_admin",
        None,
        "TemplateOS Demo Institute",
        "Platform Administrator",
    ),
    DemoUserDefinition(
        "SIT_ORG_ADMIN",
        "Demo Organization Admin",
        "org_admin",
        None,
        "TemplateOS Demo Institute",
        "Organization Administrator",
    ),
    DemoUserDefinition(
        "SIT_DEPARTMENT_ADMIN",
        "Demo Department Admin",
        "department_admin",
        "Computer Science",
        "TemplateOS Demo Institute",
        "Department Administrator",
    ),
    DemoUserDefinition(
        "SIT_FACULTY",
        "Demo Faculty",
        "faculty",
        "Computer Science",
        "TemplateOS Demo Institute",
        "Assistant Professor",
    ),
    DemoUserDefinition(
        "SIT_STUDENT",
        "Demo Student",
        "student",
        "Computer Science",
        "TemplateOS Demo Institute",
        "Student",
    ),
    DemoUserDefinition(
        "SIT_APPROVER",
        "Demo Approver",
        "approver",
        "Academic Affairs",
        "TemplateOS Demo Institute",
        "Document Approver",
    ),
    DemoUserDefinition(
        "SIT_NORMAL_USER",
        "Demo User",
        "normal_user",
        None,
        "TemplateOS Demo Institute",
        None,
    ),
)


def build_demo_user_seeds(values: Mapping[str, str | None]) -> tuple[DemoUserSeed, ...]:
    missing_variables: list[str] = []
    seeds: list[DemoUserSeed] = []

    for definition in DEMO_USER_DEFINITIONS:
        email_variable = f"{definition.environment_prefix}_EMAIL"
        password_variable = f"{definition.environment_prefix}_PASSWORD"
        email = values.get(email_variable)
        password = values.get(password_variable)
        if not email:
            missing_variables.append(email_variable)
        if not password:
            missing_variables.append(password_variable)
        if not email or not password:
            continue
        if len(password) < 8:
            raise ValueError(f"{password_variable} must contain at least 8 characters")

        seeds.append(
            DemoUserSeed(
                email=email,
                password=password,
                full_name=definition.full_name,
                role=definition.role,
                department=definition.department,
                organization=definition.organization,
                job_title=definition.job_title,
                preferences={
                    "default_document_format": "docx",
                    "email_notifications": False,
                },
            )
        )

    if missing_variables:
        names = ", ".join(missing_variables)
        raise ValueError(f"Missing demo credential environment variables: {names}")
    return tuple(seeds)


def seed_demo_users(db: Session, seeds: Sequence[DemoUserSeed]) -> list[User]:
    seeded_users: list[User] = []
    for seed in seeds:
        if seed.role not in USER_ROLES:
            raise ValueError(f"Unsupported user role: {seed.role}")

        email = seed.email.strip().lower()
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            user = User(email=email, full_name=seed.full_name.strip())
            db.add(user)

        user.full_name = seed.full_name.strip()
        user.role = seed.role
        user.department = seed.department
        user.organization = seed.organization
        user.job_title = seed.job_title
        user.phone = seed.phone
        user.avatar_url = seed.avatar_url
        user.signature_path = seed.signature_path
        user.preferences = seed.preferences
        if not verify_password(seed.password, user.hashed_password):
            user.hashed_password = hash_password(seed.password)
        seeded_users.append(user)

    db.commit()
    for user in seeded_users:
        db.refresh(user)
    return seeded_users
