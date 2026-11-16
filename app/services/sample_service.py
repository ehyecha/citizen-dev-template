"""예시 업무 로직. 계산, 저장, 조회는 routers 가 아니라 여기에 둔다."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SampleItem
from app.schemas import SampleItemCreate

logger = logging.getLogger(__name__)

PAGE_SIZE = 50  # 한 번에 최대 100건


def list_items(db: Session, page: int = 1) -> dict:
    page = max(page, 1)
    total = db.scalar(select(func.count()).select_from(SampleItem)) or 0
    rows = db.scalars(
        select(SampleItem)
        .order_by(SampleItem.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    return {
        "rows": rows,
        "page": page,
        "total": total,
        "has_prev": page > 1,
        "has_next": page * PAGE_SIZE < total,
    }


def create_item(db: Session, data: SampleItemCreate) -> SampleItem:
    item = SampleItem(name=data.name, quantity=data.quantity)
    db.add(item)
    db.commit()
    logger.info("sample_item_created", extra={"item_id": item.id})
    return item
