from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.data_reset_service import DataResetService
from app.services.file_parser import FileParserService
from app.services.import_service import ImportService
from app.web import templates


router = APIRouter(prefix="/import", tags=["import"])
file_parser = FileParserService()
import_service = ImportService()
data_reset_service = DataResetService()


@router.get("/", response_class=HTMLResponse)
def import_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "imports/index.html",
        {"request": request, "result": None, "error": None, "reset_result": None},
    )


@router.post("/", response_class=HTMLResponse)
async def import_file(
    request: Request,
    file: UploadFile = File(...),
    contract_file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        content = await file.read()
        dataframe = file_parser.read_dataframe(file.filename or "", content)
        contract_dataframe = None
        if contract_file and contract_file.filename:
            contract_content = await contract_file.read()
            if contract_content:
                contract_dataframe = file_parser.read_dataframe(contract_file.filename or "", contract_content)
        result = import_service.import_dataframe(db, dataframe, contract_dataframe=contract_dataframe)
        return templates.TemplateResponse(
            request,
            "imports/index.html",
            {
                "request": request,
                "result": result,
                "error": None,
                "filename": file.filename,
                "contract_filename": contract_file.filename if contract_file and contract_file.filename else None,
                "reset_result": None,
            },
        )
    except Exception as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "imports/index.html",
            {
                "request": request,
                "result": None,
                "error": str(exc),
                "filename": file.filename if file else None,
                "contract_filename": contract_file.filename if contract_file and contract_file.filename else None,
                "reset_result": None,
            },
            status_code=400,
        )


@router.post("/reset", response_class=HTMLResponse)
def reset_imported_data(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    try:
        reset_result = data_reset_service.reset_all_imported_data(db)
        return templates.TemplateResponse(
            request,
            "imports/index.html",
            {
                "request": request,
                "result": None,
                "error": None,
                "filename": None,
                "contract_filename": None,
                "reset_result": reset_result,
            },
        )
    except Exception as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "imports/index.html",
            {
                "request": request,
                "result": None,
                "error": f"Не удалось очистить данные: {exc}",
                "filename": None,
                "contract_filename": None,
                "reset_result": None,
            },
            status_code=400,
        )
