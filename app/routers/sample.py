"""예시 화면·주소. 요청을 받고 services 를 부른 뒤 화면을 돌려주기만 한다."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import SampleItemCreate
from app.services import sample_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def item_list(request: Request, page: int = 1, db: Session = Depends(get_db)):
    result = sample_service.list_items(db, page=page)
    return templates.TemplateResponse(request, "sample_list.html", {"result": result})


@router.post("/items")
def item_create(
    request: Request,
    name: str = Form(""),
    quantity: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        data = SampleItemCreate(name=name.strip(), quantity=quantity)
    except ValidationError:
        result = sample_service.list_items(db)
        return templates.TemplateResponse(
            request,
            "sample_list.html",
            {"result": result, "message": "입력한 내용을 다시 확인해 주세요."},
            status_code=400,
        )
    sample_service.create_item(db, data)
    return RedirectResponse("/", status_code=303)
