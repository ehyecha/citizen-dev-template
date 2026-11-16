"""설정. 모든 설정은 여기서만 환경변수로 읽는다."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"  # local / dev / prod
    # 기본값: 이 폴더의 local.db 파일 (내 PC 전용 DB, 설치 불필요).
    # 서버(PostgreSQL)에 연결할 때만 .env 의 DATABASE_URL 로 바꾼다.
    database_url: SecretStr = SecretStr("sqlite:///./local.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
