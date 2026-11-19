# Python FastAPI 개발 기준 (시민개발자용 요약본)

> 사내 직원이 만드는 **간단한 웹 도구**를 위한 상세 기준입니다.
> 사내 개발자용 정식 FastAPI 가이드를 이 템플릿에 맞게 줄인 요약본입니다.
> Claude Code 가 필요할 때만 참고합니다.
>
> **`CLAUDE.md` 와 내용이 다르면 항상 `CLAUDE.md` 가 우선합니다.**

---

## 이 문서를 보는 때

| 이럴 때 | 볼 곳 |
|---|---|
| 파일·함수·변수 이름을 지을 때 | 1장 |
| 화면·주소·업무 로직 코드를 나눠 쓸 때 | 2장 |
| 입력값 검증, 목록 화면(페이지 나누기)을 만들 때 | 3장 |
| 오류 처리를 할 때 | 4장 |
| 설정·환경변수·비밀정보를 다룰 때 | 5장 |
| DB 테이블을 만들거나 바꿀 때 | 6장 |
| 로그를 남길 때 | 7장 |
| 테스트를 만들 때 | 8장 |

> 이 템플릿에서 **만들지 않는 것**: 다른 사내 시스템 연계, 자체 로그인, 배포 설정. `Dockerfile` 은 템플릿에 들어 있고 직원이 고치지 않으며, 이미지는 `이미지 만들기.bat` 으로 만든다.
> 요청을 받으면 만들지 말고 담당자 문의를 안내합니다. <!-- TODO: 문의처 -->

---

## 1. 이름 짓기와 코드 스타일

| 대상 | 규칙 | 예시 |
|---|---|---|
| 파일 | 소문자 + 밑줄(snake_case) | `order_service.py` |
| 클래스 | 단어마다 대문자(PascalCase) | `OrderService` |
| 함수, 변수 | 소문자 + 밑줄 | `get_order_by_id` |
| 상수 | 대문자 + 밑줄 | `MAX_PAGE_SIZE` |
| 입력 형식 | `<대상><동작>Request` | `OrderCreateRequest` |
| 출력 형식 | `<대상>Response` | `OrderResponse` |
| DB 테이블, 컬럼 | 소문자 + 밑줄 | `order_item`, `created_at` |

- 모든 함수에 타입 표시를 붙입니다. 예) `def get_order(order_id: int) -> Order:`
- 함수 이름 관례: 조회 `get_` (없으면 오류), `find_` (없으면 `None`), 생성 `create_`, 수정 `update_`, 삭제 `delete_`
- 코드 정리: `uv run ruff format . && uv run ruff check .`

---

## 2. 역할 나누기 (routers / services)

```
app/
├── main.py           # 앱 시작점
├── core/config.py    # 설정
├── routers/          # 화면·주소 (요청을 받고 결과를 돌려주기만 함)
├── services/         # 업무 로직 (계산, 저장, 조회)
├── models.py         # DB 테이블
├── schemas.py        # 입력/출력 형식
├── templates/        # HTML 화면
└── static/           # CSS, JS, 이미지
```

- **routers**: 요청 받기 → services 호출 → 화면(HTML) 돌려주기. 업무 로직과 DB 직접 접근을 넣지 않습니다.
- **services**: 업무 로직과 DB 작업을 합니다. 화면(HTML)을 모릅니다.

```python
# app/routers/orders.py
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import order_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/orders")
def order_list(request: Request, page: int = 1, db: Session = Depends(get_db)):
    result = order_service.list_orders(db, page=page)
    return templates.TemplateResponse(request, "orders.html", {"result": result})
```

```python
# app/services/order_service.py
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order

logger = logging.getLogger(__name__)
PAGE_SIZE = 50  # 한 번에 최대 100건


def list_orders(db: Session, page: int = 1) -> dict:
    page = max(page, 1)
    total = db.scalar(select(func.count()).select_from(Order))
    rows = db.scalars(
        select(Order).order_by(Order.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).all()
    return {"items": rows, "page": page, "total": total, "page_size": PAGE_SIZE}
```

---

## 3. 입력 검증과 목록 화면

- 사용자가 입력하는 값은 **항상 `schemas.py` 의 Pydantic 형식**으로 검증합니다.
- 입력 항목마다 범위를 정합니다 (`Field`).
- DB 테이블 객체를 화면·응답에 그대로 넘기지 않고 형식(schema)을 거칩니다.

```python
# app/schemas.py
from datetime import date

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    item_name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=100000)
    received_on: date
```

- **목록 화면은 반드시 페이지를 나눕니다.** 한 번에 최대 **100건**입니다.
- 화면에 "이전 / 다음" 버튼과 전체 건수를 보여 줍니다.

---

## 4. 오류 처리

- 사용자에게 **스택트레이스, SQL, 파일 경로 등 내부 오류 내용을 보여 주지 않습니다.**
- 대신 쉬운 안내 문구를 보여 줍니다. 예) "처리 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."
- 자세한 오류는 **로그에만** 남깁니다 (개인정보·비밀정보 제외).
- 오류 처리는 `main.py` 에서 한 번에 등록하고, 각 화면에서 따로 처리하지 않습니다.

```python
# app/main.py (일부)
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError):
    return HTMLResponse("입력한 내용을 다시 확인해 주세요.", status_code=400)


@app.exception_handler(Exception)
async def handle_unknown(request: Request, exc: Exception):
    logger.exception("unexpected_error")
    return HTMLResponse("처리 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요.", status_code=500)
```

---

## 5. 설정과 비밀정보 (가장 중요)

- 비밀번호, API 키, 토큰, DB 접속 정보를 **코드에 쓰지 않습니다.**
- 모든 설정은 `app/core/config.py` 에서만 읽습니다. 다른 곳에서 `os.environ` 을 직접 쓰지 않습니다.
- 비밀 값은 `SecretStr` 로 받아 로그에 찍혀도 가려지게 합니다.
- `.env` 파일은 Git 에 올리지 않습니다 (`.gitignore` 에 포함). 필요한 **키 이름만** `.env.example` 에 적습니다.
- 실수로 올렸다면 즉시 키를 폐기·재발급하고 담당자에게 알립니다.

```python
# app/core/config.py
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"  # local / dev / prod
    database_url: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## 6. 데이터베이스 (PostgreSQL)

- DB 는 **PostgreSQL** 입니다. 접속 정보는 환경변수 `DATABASE_URL` 로만 받습니다. 내 PC 에서는 `docker compose up -d db` 로 켠 PostgreSQL 컨테이너를 씁니다.
- SQLAlchemy 2.x 방식(`select()`, `Mapped[]`)을 씁니다.
- **SQL 을 문자열로 이어 붙이지 않습니다.** 반드시 SQLAlchemy 문법이나 파라미터 바인딩을 씁니다.
- **테이블을 만들거나 바꿀 때는 Alembic 으로만** 합니다. DB 를 직접 고치지 않습니다.
  - `uv run alembic revision --autogenerate -m "add order table"` → 만들어진 파일을 확인한 뒤 저장
  - `uv run alembic upgrade head` → 적용
  - 이미 적용한 마이그레이션 파일은 수정하지 않습니다.
- 모든 테이블에 기본키(`id`), `created_at`, `updated_at` 을 둡니다.

```python
# app/models.py
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_name: Mapped[str] = mapped_column(index=True)
    quantity: Mapped[int]
    received_on: Mapped[date]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

> 개인정보(주민번호, 연락처, 급여, 계좌)나 회사 기밀(배합비, 원가, 레시피) 컬럼이 필요하면 **만들기 전에 담당자에게 문의**합니다.

---

## 7. 로그

- `print` 를 쓰지 않고 `logging` 을 씁니다.
- **개인정보, 비밀번호, 토큰을 로그에 남기지 않습니다.**

| 레벨 | 쓰는 때 |
|---|---|
| ERROR | 바로 확인이 필요한 문제 |
| WARNING | 처리는 했지만 주의가 필요한 상황 |
| INFO | 주요 동작 (저장 완료 등) |
| DEBUG | 개발할 때만 |

```python
import logging

logger = logging.getLogger(__name__)
logger.info("order_created", extra={"order_id": order.id})  # 이름·연락처 같은 값은 넣지 않는다
```

---

## 8. 테스트

- 새 기능을 만들면 `tests/` 에 **간단한 테스트를 함께** 만듭니다.
- 최소 기준: services 의 핵심 동작 1개 이상 + 화면 주소 1개 이상(응답 코드 200 확인).
- 실행: `uv run pytest` 가 통과해야 합니다.
- `/health` 주소는 삭제하거나 수정하지 않습니다 (배포 시스템이 사용).

```python
# tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
```

---

## 문서 정보

| 항목 | 내용 |
|---|---|
| 대상 | 시민개발자용 간단한 웹 도구 |
| 기준 문서 | 사내 개발자용 FastAPI 가이드 (요약·수정본) |
| 담당 | <!-- TODO --> |
| 최종 수정 | 2026-11-13 |
