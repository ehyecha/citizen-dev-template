"""DB 연결. 실제로 DB 를 쓸 때 처음 연결한다 (/health 는 DB 없이도 동작)."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)


def upgrade_local_db() -> None:
    """내 PC(APP_ENV=local)일 때만, 앱이 시작될 때 테이블을 자동으로 만든다 (Alembic 기록 사용).

    서버 DB(PostgreSQL)는 자동으로 바꾸지 않는다. 담당자가 정한 절차로 적용한다.
    """
    if get_settings().app_env != "local":
        return
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")


def get_db() -> Iterator[Session]:
    """화면(routers)에서 DB 세션을 받을 때 쓴다."""
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        yield db
