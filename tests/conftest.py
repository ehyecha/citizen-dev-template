import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import Base


def _test_db_url():
    """내 DB 이름 뒤에 _test 를 붙인 '테스트 전용 DB' 주소. 내가 쓰는 데이터는 건드리지 않는다."""
    url = make_url(get_settings().database_url.get_secret_value())
    return url, url.set(database=f"{url.database}_test")


@pytest.fixture(scope="session")
def test_engine():
    """내 PC 의 PostgreSQL(docker compose up -d db)에 테스트 전용 DB 를 만들어 쓴다."""
    try:
        admin_url, test_url = _test_db_url()
        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_url.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
        admin.dispose()
    except Exception:  # 설정 누락·DB 꺼짐 모두 쉬운 안내로 바꾼다
        pytest.exit(
            "테스트용 PostgreSQL 에 연결하지 못했습니다. "
            ".env 가 있는지, `docker compose up -d db` 로 DB 를 켰는지 확인하세요.",
            returncode=2,
        )
    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine):
    """테스트마다 빈 테이블을 새로 만들고, 끝나면 지운다."""
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
