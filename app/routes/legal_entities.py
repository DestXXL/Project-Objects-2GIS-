from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.services.manual_data_service import ManualDataService
from app.web import templates


router = APIRouter(prefix="/legal-entities", tags=["legal-entities"])
manual_data_service = ManualDataService()


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
    saved: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = LegalEntityRepository.get_by_id(db, legal_entity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    return templates.TemplateResponse(
        request,
        "legal_entities/detail.html",
        {
            "request": request,
            "item": item,
            "success_message": "Изменения сохранены." if saved else None,
            "error_message": None,
            "form_values": {},
        },
    )


@router.post("/{legal_entity_id}/edit", response_class=HTMLResponse)
async def legal_entity_update(
    legal_entity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    item = LegalEntityRepository.get_by_id(db, legal_entity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    form_data = dict(await request.form())
    try:
        manual_data_service.update_legal_entity(db, item, form_data)
        db.commit()
        return RedirectResponse(url=f"/legal-entities/{legal_entity_id}?saved=1", status_code=303)
    except ValueError as exc:
        db.rollback()
        item = LegalEntityRepository.get_by_id(db, legal_entity_id)
        return templates.TemplateResponse(
            request,
            "legal_entities/detail.html",
            {
                "request": request,
                "item": item,
                "success_message": None,
                "error_message": str(exc),
                "form_values": form_data,
            },
            status_code=400,
        )
