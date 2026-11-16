from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import get_engine
from app.main import app


def test_local_db_tables_are_created_on_start(tmp_path, monkeypatch):
    """로컬 DB 파일일 때는 앱을 켜기만 해도 테이블이 자동으로 만들어진다."""
    db_file = tmp_path / "test_local.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        with TestClient(app) as client:  # with 로 열어야 앱 시작 동작이 실행된다
            assert client.get("/").status_code == 200
        assert db_file.exists()
    finally:
        get_engine().dispose()
        get_settings.cache_clear()
        get_engine.cache_clear()
