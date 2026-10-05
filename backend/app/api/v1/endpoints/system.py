from fastapi import APIRouter

from app.db.session import check_database_connection

router = APIRouter()


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.get("/db-check")
def db_check() -> dict[str, str | bool]:
    is_connected, detail = check_database_connection()
    return {
        "ok": is_connected,
        "message": detail,
    }
