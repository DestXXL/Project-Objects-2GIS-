from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.config import STATIC_DIR
from app.web import templates


router = APIRouter(tags=["pwa"])

PWA_DIR = STATIC_DIR / "pwa"
ICONS_DIR = STATIC_DIR / "icons"


@router.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    response = FileResponse(
        path=PWA_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


@router.get("/service-worker.js")
def service_worker() -> FileResponse:
    response = FileResponse(
        path=PWA_DIR / "service-worker.js",
        media_type="application/javascript",
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


@router.get("/offline", response_class=HTMLResponse)
def offline_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "offline.html",
        {"request": request},
    )


@router.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(path=ICONS_DIR / "app-icon.svg", media_type="image/svg+xml")

