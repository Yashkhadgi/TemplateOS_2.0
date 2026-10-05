"""
Reusable template view-access checks (V1.3 Phase 1 — Member 2).

Extracted verbatim from the inline has_access ladder that used to live in
get_template (app/api/v1/endpoints/templates.py) so GET /{id}/fields can
enforce the same rules without duplicating them. Behavior is identical.
"""

from app.models.template import Template
from app.models.user import User


def user_can_view_template(user: User, template: Template) -> bool:
    """Return True if the user may view the template (RBAC visibility rules)."""
    if user.role == "super_admin":
        return True
    if template.uploaded_by == user.id or template.visibility == "public":
        return True
    if (
        template.visibility == "department"
        and user.department
        and template.uploader.department == user.department
    ):
        return True
    if (
        template.visibility == "organization"
        and user.organization
        and template.uploader.organization == user.organization
    ):
        return True
    if (
        template.visibility == "group"
        and user.role
        and template.uploader.role == user.role
    ):
        return True
    return False
