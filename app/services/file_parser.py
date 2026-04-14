from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

import pandas as pd


class FileParserService:
    SUPPORTED_EXTENSIONS = {".xlsx", ".csv"}

    def read_dataframe(self, filename: str, content: bytes) -> pd.DataFrame:
        suffix = Path(filename).suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise ValueError("Поддерживаются только файлы .xlsx и .csv")

        if suffix == ".xlsx":
            return pd.read_excel(BytesIO(content))

        last_error: Optional[Exception] = None
        for encoding in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                return pd.read_csv(BytesIO(content), encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc

        raise ValueError("Не удалось определить кодировку CSV") from last_error
