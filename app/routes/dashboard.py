from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.dashboard_service import DashboardService
from app.web import templates


router = APIRouter()
dashboard_service = DashboardService()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    stats = dashboard_service.get_stats(db)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "stats": stats},
    )
