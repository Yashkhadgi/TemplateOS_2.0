import os
from pathlib import Path
import sys

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.demo_seed import build_demo_user_seeds, seed_demo_users
from app.db.session import SessionLocal


def main() -> None:
    file_values = dotenv_values(ROOT_DIR / ".env")
    values: dict[str, str | None] = {**file_values, **os.environ}
    try:
        seeds = build_demo_user_seeds(values)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    with SessionLocal() as db:
        users = seed_demo_users(db, seeds)
    print(f"Seeded {len(users)} development/demo users.")


if __name__ == "__main__":
    main()
