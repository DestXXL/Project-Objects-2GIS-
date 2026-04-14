from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.web import templates


router = APIRouter(prefix="/legal-entities", tags=["legal-entities"])


@router.get("/", response_class=HTMLResponse)
def legal_entity_list(
    request: Request,
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    items = LegalEntityRepository.list_with_counts(db, q)
    return templates.TemplateResponse(
        request,
        "legal_entities/list.html",
        {"request": request, "items": items, "query": q or ""},
    )


@router.get("/{legal_entity_id}", response_class=HTMLResponse)
def legal_entity_detail(
    legal_entity_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = LegalEntityRepository.get_by_id(db, legal_entity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    return templates.TemplateResponse(
        request,
        "legal_entities/detail.html",
        {"request": request, "item": item},
    )
