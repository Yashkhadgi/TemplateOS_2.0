from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True, "Database connection successful."
    except Exception as exc:  # pragma: no cover - operational path
        return False, str(exc)
