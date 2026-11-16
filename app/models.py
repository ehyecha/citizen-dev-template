"""DB 테이블. 테이블을 바꾸면 반드시 Alembic 마이그레이션을 만든다."""

from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SampleItem(Base):
    """예시 테이블. 실제 도구를 만들 때 이름과 컬럼을 바꾸거나 지운다."""

    __tablename__ = "sample_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
