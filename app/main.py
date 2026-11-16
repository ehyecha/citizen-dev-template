"""앱 시작점."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.database import upgrade_local_db
from app.routers import sample

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    upgrade_local_db()  # 로컬 DB 파일일 때만 테이블 자동 생성
    yield


app = FastAPI(title="사내 웹 도구", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# 로그인은 사내 SSO 가 앞에서 처리하므로 여기에 로그인 코드를 만들지 않는다.


@app.get("/health", include_in_schema=False)
def health() -> dict:
    """배포 시스템이 사용하는 주소. 삭제하거나 수정하지 않는다."""
    return {"status": "ok"}


app.include_router(sample.router)


@app.exception_handler(Exception)
async def handle_unknown(request: Request, exc: Exception) -> HTMLResponse:
    # 자세한 오류는 로그에만 남기고, 사용자에게는 쉬운 안내만 보여준다.
    logger.exception("unexpected_error")
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": "처리 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."},
        status_code=500,
    )
