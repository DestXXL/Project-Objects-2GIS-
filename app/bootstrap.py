from __future__ import annotations

from alembic import command
from alembic.config import Config
from pathlib import Path

from app.config import BASE_DIR, database_url_for_path
from app import db as database


def ensure_database_ready(database_path: str | Path | None = None) -> None:
    alembic_ini = BASE_DIR / "alembic.ini"
    if database_path is not None:
        database.configure_database(database_path)
    target_url = database.current_database_url

    try:
        if alembic_ini.exists():
            config = Config(str(alembic_ini))
            config.set_main_option("script_location", str(BASE_DIR / "alembic"))
            config.set_main_option("sqlalchemy.url", target_url)
            command.upgrade(config, "head")
        else:
            database.Base.metadata.create_all(bind=database.engine)
    except Exception:
        database.Base.metadata.create_all(bind=database.engine)
