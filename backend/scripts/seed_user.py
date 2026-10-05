import argparse
from pathlib import Path
import sys

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import USER_ROLES, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a TemplateOS seed user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--role", choices=USER_ROLES, default="normal_user")
    args = parser.parse_args()

    if len(args.password) < 8:
        parser.error("--password must contain at least 8 characters")

    email = args.email.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            user = User(email=email, full_name=args.full_name.strip())
            db.add(user)
        user.full_name = args.full_name.strip()
        user.role = args.role
        user.hashed_password = hash_password(args.password)
        db.commit()
        print(f"Seeded {user.email} with role {user.role}.")


if __name__ == "__main__":
    main()
