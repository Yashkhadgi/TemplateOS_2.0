from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import Session

from app.models.template import Template, TEMPLATE_STATUSES
from app.models.user import User
from app.schemas.template import TemplateCreate

# Forward-only status ladder (V1.3 Phase 2). "archived"/"locked" are terminal
# admin states — never moved by automated transitions.
_STATUS_RANK: dict[str, int] = {
    "uploaded": 0,
    "placeholder_detected": 1,
    "field_configured": 2,
    "active": 3,
    "archived": 4,
    "locked": 5,
}


def create_template(db: Session, data: TemplateCreate) -> Template:
    """
    Insert a new template row.
    data.original_file_path must be a relative string path, never binary.
    """
    db_obj = Template(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_template_by_id(db: Session, template_id: int) -> Template | None:
    """Return Template or None."""
    result = db.execute(select(Template).where(Template.id == template_id))
    return result.scalar_one_or_none()


def get_templates_by_user(db: Session, user_id: int) -> list[Template]:
    """Return all templates uploaded by the given user, newest first."""
    result = db.execute(
        select(Template)
        .where(Template.uploaded_by == user_id)
        .order_by(Template.created_at.desc())
    )
    return list(result.scalars().all())


def get_public_templates(
    db: Session, limit: int = 50, offset: int = 0
) -> list[Template]:
    """
    Return publicly visible templates, newest first.
    Used by the template library listing in Phase 3.
    """
    result = db.execute(
        select(Template)
        .where(Template.visibility == "public")
        .where(Template.status.in_(["active", "uploaded", "field_configured"]))
        .order_by(Template.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


def get_templates_by_category(
    db: Session,
    category: str,
    user_id: int | None = None,
    limit: int = 50,
) -> list[Template]:
    """
    Return templates filtered by category.
    If user_id is provided, returns only that user's templates in the category.
    """
    query = select(Template).where(Template.category == category)
    if user_id is not None:
        query = query.where(Template.uploaded_by == user_id)
    query = query.order_by(Template.created_at.desc()).limit(limit)
    result = db.execute(query)
    return list(result.scalars().all())


def _escape_like(value: str) -> str:
    """Escape special LIKE characters so they match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_library_templates(
    db: Session,
    user_id: int,
    search: str | None = None,
    category: str | None = None,
    visibility: str | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Template], int]:
    """
    Return templates visible to the given user.

    Visibility rules for V1.2:
    - Always include user's own templates (any visibility)
    - Always include public templates from other users
    - Do NOT include other users' private/org/department/group templates
      (organization and group-based visibility is deferred to V1.9)

    Supports:
    - Search: case-insensitive partial match on template name
    - Category filter: exact match
    - Visibility filter: exact match
    - Status filter: exact match
    - Pagination: page + limit based

    Returns: (list_of_templates, total_count)
    """
    user = db.get(User, user_id)
    if not user:
        return [], 0

    if user.role != "super_admin":
        conditions = [
            Template.uploaded_by == user_id,
            Template.visibility == "public",
        ]

        if user.department:
            conditions.append(
                and_(
                    Template.visibility == "department",
                    Template.uploader.has(User.department == user.department),
                )
            )

        if user.organization:
            conditions.append(
                and_(
                    Template.visibility == "organization",
                    Template.uploader.has(User.organization == user.organization),
                )
            )

        # Optional: handling "group" visibility if user has a role/group
        if user.role:
            conditions.append(
                and_(
                    Template.visibility == "group",
                    Template.uploader.has(User.role == user.role),
                )
            )

        visibility_filter = or_(*conditions)

    if user.role == "super_admin":
        query = select(Template)
    else:
        query = select(Template).where(visibility_filter)

    if search:
        safe_search = _escape_like(search)
        query = query.where(Template.name.ilike(f"%{safe_search}%"))
    if category:
        query = query.where(Template.category == category)
    if visibility:
        query = query.where(Template.visibility == visibility)
    if status:
        query = query.where(Template.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    offset = (page - 1) * limit
    query = query.order_by(Template.created_at.desc()).offset(offset).limit(limit)

    result = db.execute(query)
    templates = list(result.scalars().all())
    return templates, total


def get_template_count_by_user(db: Session, user_id: int) -> int:
    """Return the total number of templates uploaded by a user."""
    result = db.execute(
        select(func.count(Template.id)).where(Template.uploaded_by == user_id)
    )
    return result.scalar() or 0


def search_templates(
    db: Session,
    query_text: str,
    user_id: int | None = None,
    limit: int = 20,
) -> list[Template]:
    """
    Search templates by name (case-insensitive partial match).
    If user_id is provided, only searches that user's templates.
    Otherwise searches all public templates.
    """
    base = select(Template)
    if user_id is not None:
        base = base.where(Template.uploaded_by == user_id)
    else:
        base = base.where(Template.visibility == "public")

    safe_search = _escape_like(query_text)
    base = base.where(Template.name.ilike(f"%{safe_search}%"))

    base = base.order_by(Template.created_at.desc()).limit(limit)
    result = db.execute(base)
    return list(result.scalars().all())


def set_processed_path(db: Session, template: Template, path: str) -> Template:
    """
    Record the processed (cleaned) DOCX path on the template.
    The original_file_path is never touched — cleaning always preserves it.
    """
    template.processed_file_path = path
    db.commit()
    db.refresh(template)
    return template


def advance_status(db: Session, template: Template, target: str) -> Template:
    """
    Move template.status FORWARD along the ladder only:
    uploaded < placeholder_detected < field_configured < active ( < archived/locked ).

    Never downgrades: if template.status already ranks >= target, the current
    status is kept (returned unchanged). Raises ValueError for unknown statuses.
    """
    if target not in TEMPLATE_STATUSES:
        raise ValueError(f"Unknown template status: {target}")
    if _STATUS_RANK[target] > _STATUS_RANK[template.status]:
        template.status = target
        db.commit()
        db.refresh(template)
    return template
