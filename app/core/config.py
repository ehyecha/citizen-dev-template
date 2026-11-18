"""설정. 모든 설정은 여기서만 환경변수로 읽는다."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"  # local / dev / prod
    # PostgreSQL 접속 주소. 코드에 쓰지 않고 .env(내 PC) 또는 서버 환경변수에서만 읽는다.
    database_url: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()
