# 사내 웹 도구 이미지 (템플릿 공용). 꼭 필요할 때만 고치세요. 모르면 담당자에게 문의하세요.
# 주의: 이 파일에서 .env 나 비밀정보를 이미지에 넣지 마세요. (.dockerignore 는 고치지 마세요)
# 이미지 안에는 .env 나 접속 정보가 들어가지 않습니다. DB 주소는 서버에서 환경변수 DATABASE_URL 로 넣습니다.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /srv

# 패키지 설치 (개발용 도구는 제외)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 앱 코드. 테이블 적용(alembic)을 서버에서 할 수 있도록 alembic 도 함께 넣는다.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONPATH="/srv"

# 관리자 권한이 아닌 일반 사용자로 실행
RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
