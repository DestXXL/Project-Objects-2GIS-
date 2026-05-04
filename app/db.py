from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_PATH, DATABASE_URL, database_url_for_path


class Base(DeclarativeBase):
    pass


current_database_path = DATABASE_PATH
current_database_url = DATABASE_URL
engine = create_engine(current_database_url, connect_args={"check_same_thread": False}, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def configure_database(database_path: str | Path) -> None:
    global current_database_path, current_database_url, engine

    new_path = Path(database_path)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_url = database_url_for_path(new_path)
    if new_path == current_database_path:
        return

    engine.dispose()
    current_database_path = new_path
    current_database_url = new_url
    engine = create_engine(current_database_url, connect_args={"check_same_thread": False}, future=True)
    SessionLocal.configure(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
