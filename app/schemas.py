"""입력/출력 형식. 사용자가 입력하는 값은 여기서 검증한다."""

from pydantic import BaseModel, Field


class SampleItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=100000)
