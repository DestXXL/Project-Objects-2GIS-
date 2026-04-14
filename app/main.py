from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.routes.dashboard import router as dashboard_router
from app.routes.imports import router as imports_router
from app.routes.legal_entities import router as legal_entities_router
from app.routes.pwa import router as pwa_router
from app.routes.real_estate import router as real_estate_router
from app.routes.waste_objects import router as waste_objects_router


app = FastAPI(title="Реестр объектов недвижимости и отходов")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(dashboard_router)
app.include_router(imports_router)
app.include_router(pwa_router)
app.include_router(real_estate_router)
app.include_router(waste_objects_router)
app.include_router(legal_entities_router)
