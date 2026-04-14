from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.repositories.real_estate_repository import RealEstateRepository
from app.web import templates


router = APIRouter(prefix="/real-estate", tags=["real-estate"])


@router.get("/", response_class=HTMLResponse)
def real_estate_list(
    request: Request,
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    items = RealEstateRepository.list_with_counts(db, q)
    return templates.TemplateResponse(
        request,
        "real_estate/list.html",
        {"request": request, "items": items, "query": q or ""},
    )


@router.get("/{real_estate_id}", response_class=HTMLResponse)
def real_estate_detail(
    real_estate_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = RealEstateRepository.get_by_id(db, real_estate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    return templates.TemplateResponse(
        request,
        "real_estate/detail.html",
        {"request": request, "item": item},
    )
