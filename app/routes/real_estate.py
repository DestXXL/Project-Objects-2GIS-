from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.repositories.real_estate_repository import RealEstateRepository
from app.services.manual_data_service import ManualDataService
from app.web import templates


router = APIRouter(prefix="/real-estate", tags=["real-estate"])
manual_data_service = ManualDataService()


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
    saved: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = RealEstateRepository.get_by_id(db, real_estate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    return templates.TemplateResponse(
        request,
        "real_estate/detail.html",
        {
            "request": request,
            "item": item,
            "success_message": "Изменения сохранены." if saved else None,
            "error_message": None,
            "form_values": {},
        },
    )


@router.post("/{real_estate_id}/edit", response_class=HTMLResponse)
async def real_estate_update(
    real_estate_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    item = RealEstateRepository.get_by_id(db, real_estate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")

    form_data = dict(await request.form())
    try:
        manual_data_service.update_real_estate(db, item, form_data)
        db.commit()
        return RedirectResponse(url=f"/real-estate/{real_estate_id}?saved=1", status_code=303)
    except ValueError as exc:
        db.rollback()
        item = RealEstateRepository.get_by_id(db, real_estate_id)
        return templates.TemplateResponse(
            request,
            "real_estate/detail.html",
            {
                "request": request,
                "item": item,
                "success_message": None,
                "error_message": str(exc),
                "form_values": form_data,
            },
            status_code=400,
        )
