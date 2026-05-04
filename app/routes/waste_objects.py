from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.repositories.waste_object_repository import WasteObjectRepository
from app.services.manual_data_service import ManualDataService
from app.services.waste_object_grouping_service import WasteObjectGroupingService
from app.web import templates


router = APIRouter(prefix="/waste-objects", tags=["waste-objects"])
manual_data_service = ManualDataService()


@router.get("/", response_class=HTMLResponse)
def waste_object_list(
    request: Request,
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    items = WasteObjectRepository.list(db, q)
    grouping = WasteObjectGroupingService.split_by_enrichment(items)
    return templates.TemplateResponse(
        request,
        "waste_objects/list.html",
        {
            "request": request,
            "items": items,
            "query": q or "",
            "enriched_items": grouping.enriched_items,
            "incomplete_items": grouping.incomplete_items,
        },
    )


@router.get("/{waste_object_id}", response_class=HTMLResponse)
def waste_object_detail(
    waste_object_id: int,
    request: Request,
    saved: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = WasteObjectRepository.get_by_id(db, waste_object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    return templates.TemplateResponse(
        request,
        "waste_objects/detail.html",
        {
            "request": request,
            "item": item,
            "success_message": "Изменения сохранены." if saved else None,
            "error_message": None,
            "form_values": {},
        },
    )


@router.post("/{waste_object_id}/edit", response_class=HTMLResponse)
async def waste_object_update(
    waste_object_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    item = WasteObjectRepository.get_by_id(db, waste_object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    form_data = dict(await request.form())
    try:
        manual_data_service.update_waste_object(db, item, form_data)
        db.commit()
        return RedirectResponse(url=f"/waste-objects/{waste_object_id}?saved=1", status_code=303)
    except ValueError as exc:
        db.rollback()
        item = WasteObjectRepository.get_by_id(db, waste_object_id)
        return templates.TemplateResponse(
            request,
            "waste_objects/detail.html",
            {
                "request": request,
                "item": item,
                "success_message": None,
                "error_message": str(exc),
                "form_values": form_data,
            },
            status_code=400,
        )
