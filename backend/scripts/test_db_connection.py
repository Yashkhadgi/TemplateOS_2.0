from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import check_database_connection


def main() -> None:
    is_connected, detail = check_database_connection()
    if is_connected:
        print("OK:", detail)
        raise SystemExit(0)

    print("ERROR:", detail)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
