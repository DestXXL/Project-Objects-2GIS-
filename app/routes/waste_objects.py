from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.repositories.waste_object_repository import WasteObjectRepository
from app.web import templates


router = APIRouter(prefix="/waste-objects", tags=["waste-objects"])


@router.get("/", response_class=HTMLResponse)
def waste_object_list(
    request: Request,
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    items = WasteObjectRepository.list(db, q)
    return templates.TemplateResponse(
        request,
        "waste_objects/list.html",
        {"request": request, "items": items, "query": q or ""},
    )


@router.get("/{waste_object_id}", response_class=HTMLResponse)
def waste_object_detail(
    waste_object_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = WasteObjectRepository.get_by_id(db, waste_object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    return templates.TemplateResponse(
        request,
        "waste_objects/detail.html",
        {"request": request, "item": item},
    )
