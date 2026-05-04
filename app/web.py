from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR
from app.utils.formatting import format_date_ru


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["date_ru"] = format_date_ru
