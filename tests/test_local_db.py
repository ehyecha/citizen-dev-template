from app.core import database
from app.core.config import get_settings

DUMMY_URL = "postgresql+psycopg://u:p@localhost:5432/test"


def _run_upgrade(monkeypatch, app_env: str) -> list:
    """upgrade_local_db 를 실행하고, Alembic 이 호출됐는지 기록해서 돌려준다."""
    calls: list = []
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DATABASE_URL", DUMMY_URL)
    monkeypatch.setattr(database.command, "upgrade", lambda *args: calls.append(args))
    get_settings.cache_clear()
    try:
        database.upgrade_local_db()
    finally:
        get_settings.cache_clear()
    return calls


def test_tables_are_created_on_start_in_local(monkeypatch):
    """내 PC(APP_ENV=local)에서는 앱을 켤 때 테이블을 자동으로 만든다."""
    assert len(_run_upgrade(monkeypatch, "local")) == 1


def test_tables_are_not_touched_on_server(monkeypatch):
    """서버(prod 등)에서는 테이블을 자동으로 바꾸지 않는다."""
    assert _run_upgrade(monkeypatch, "prod") == []
