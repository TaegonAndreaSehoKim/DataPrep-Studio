from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
    return _engine


def get_session_local() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def initialize_database() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    migrate_database(get_engine())


def migrate_database(engine) -> None:
    """Add the immutable snapshot field without changing existing local data."""
    if engine.dialect.name != "sqlite":
        return
    columns = {column["name"] for column in inspect(engine).get_columns("analysis_runs")}
    if "options_json" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE analysis_runs ADD COLUMN options_json TEXT NOT NULL DEFAULT 'null'")


def reset_database_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
