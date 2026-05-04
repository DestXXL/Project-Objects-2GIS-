from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import LegalEntity, RealEstate, WasteObject
from app.utils.formatting import format_date_ru


class ExportService:
    def export_to_excel(self, db: Session, destination: str | Path) -> Path:
        destination_path = Path(destination)
        frames = self.build_export_frames(db)

        with pd.ExcelWriter(destination_path, engine="openpyxl") as writer:
            for sheet_name, dataframe in frames.items():
                dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                self._autosize_columns(worksheet, dataframe)

        return destination_path

    def export_comparison_to_excel(self, db: Session, reference_path: str | Path, destination: str | Path) -> Path:
        destination_path = Path(destination)
        dataframe = self.build_comparison_frame(db, reference_path)

        with pd.ExcelWriter(destination_path, engine="openpyxl") as writer:
            dataframe.to_excel(writer, sheet_name="Сравнение", index=False)
            worksheet = writer.sheets["Сравнение"]
            self._autosize_columns(worksheet, dataframe)

        return destination_path

    def build_comparison_frame(self, db: Session, reference_path: str | Path) -> pd.DataFrame:
        reference_df = pd.read_excel(reference_path)
        current_by_source_row = self._current_waste_objects_by_source_row(db)
        rows: list[dict[str, object]] = []

        for dataframe_index, reference_row in reference_df.iterrows():
            source_row_index = int(dataframe_index) + 2
            current_item = current_by_source_row.get(source_row_index)
            reference_address = self._reference_address(reference_row)
            current_address = current_item.real_estate.address if current_item and current_item.real_estate else None

            rows.append(
                {
                    "№ строки 2GIS": source_row_index,
                    "Адрес": reference_address or current_address,
                    "Эталон: номер договора": self._reference_value(reference_row, "Номер договора", 24),
                    "Моя база: номер договора": current_item.contract_number if current_item else None,
                    "Эталон: 24 столбец": self._reference_value(reference_row, 24, 23),
                    "Моя база: 24 столбец": self._current_match_code(current_item) if current_item else None,
                    "Эталон: наименование объекта": self._reference_value(reference_row, "Наименование организации", 0),
                    "Моя база: наименование объекта": current_item.name if current_item else None,
                    "Моя база: сопоставление": current_item.contract_link_strategy if current_item else None,
                }
            )

        return pd.DataFrame(rows)

    def build_export_frames(self, db: Session) -> dict[str, pd.DataFrame]:
        waste_objects = list(
            db.scalars(
                select(WasteObject)
                .options(
                    joinedload(WasteObject.real_estate),
                    joinedload(WasteObject.legal_entity),
                )
                .order_by(WasteObject.id)
            ).all()
        )
        real_estates = list(
            db.scalars(
                select(RealEstate)
                .options(selectinload(RealEstate.waste_objects))
                .order_by(RealEstate.id)
            ).all()
        )
        legal_entities = list(
            db.scalars(
                select(LegalEntity)
                .options(selectinload(LegalEntity.waste_objects))
                .order_by(LegalEntity.id)
            ).all()
        )

        merged_rows = [
            {
                "ID объекта отходов": item.id,
                "Наименование объекта отходов": item.name,
                "Категория": item.category,
                "Вид отходов": item.waste_type,
                "Объем": item.calculation_value,
                "Как начисляется": item.billing_method,
                "ИНН": item.inn,
                "Номер договора": item.contract_number,
                "Дата договора": self._format_date(item.contract_date),
                "Адрес": item.real_estate.address if item.real_estate else None,
                "Район": item.real_estate.district if item.real_estate else None,
                "Город": item.real_estate.city if item.real_estate else None,
                "Улица": item.real_estate.street if item.real_estate else None,
                "Дом": item.real_estate.building if item.real_estate else None,
                "Кадастровый номер": item.real_estate.cadastral_number if item.real_estate else None,
                "Площадь": item.real_estate.area if item.real_estate else None,
                "Этажность": item.real_estate.floors if item.real_estate else None,
                "Назначение": item.real_estate.purpose if item.real_estate else None,
                "Наименование юрлица": item.legal_entity.name if item.legal_entity else None,
                "Контактное лицо": item.legal_entity.contact_person if item.legal_entity else None,
                "Телефон": item.legal_entity.phone if item.legal_entity else None,
                "Email": item.legal_entity.email if item.legal_entity else None,
            }
            for item in waste_objects
        ]

        real_estate_rows = [
            {
                "ID": item.id,
                "Адрес": item.address,
                "Район": item.district,
                "Город": item.city,
                "Улица": item.street,
                "Дом": item.building,
                "Кадастровый номер": item.cadastral_number,
                "Площадь": item.area,
                "Этажность": item.floors,
                "Назначение": item.purpose,
                "Тип объекта": item.object_type,
                "Количество связанных объектов отходов": len(item.waste_objects),
            }
            for item in real_estates
        ]

        legal_entity_rows = [
            {
                "ID": item.id,
                "ИНН": item.inn,
                "Наименование": item.name,
                "Контактное лицо": item.contact_person,
                "Телефон": item.phone,
                "Email": item.email,
                "Количество связанных объектов отходов": len(item.waste_objects),
            }
            for item in legal_entities
        ]

        waste_rows = [
            {
                "ID": item.id,
                "Наименование": item.name,
                "Категория": item.category,
                "Вид отходов": item.waste_type,
                "Объем": item.calculation_value,
                "Как начисляется": item.billing_method,
                "ИНН": item.inn,
                "Номер договора": item.contract_number,
                "Дата договора": self._format_date(item.contract_date),
                "Адрес": item.real_estate.address if item.real_estate else None,
                "Юрлицо": item.legal_entity.name if item.legal_entity else None,
                "Статус привязки договора": item.contract_link_status,
            }
            for item in waste_objects
        ]

        return {
            "Сводная выгрузка": pd.DataFrame(merged_rows),
            "Объекты отходов": pd.DataFrame(waste_rows),
            "Недвижимость": pd.DataFrame(real_estate_rows),
            "Юрлица": pd.DataFrame(legal_entity_rows),
        }

    def _current_waste_objects_by_source_row(self, db: Session) -> dict[int, WasteObject]:
        items = db.scalars(
            select(WasteObject)
            .options(joinedload(WasteObject.real_estate))
            .order_by(WasteObject.source_row_index, WasteObject.id)
        ).all()
        result: dict[int, WasteObject] = {}
        for item in items:
            result.setdefault(item.source_row_index, item)
        return result

    @staticmethod
    def _reference_value(row: pd.Series, column_name: object, fallback_index: int) -> object:
        if column_name in row.index:
            value = row[column_name]
        elif fallback_index >= 0 and len(row) > fallback_index:
            value = row.iloc[fallback_index]
        else:
            value = None
        return None if pd.isna(value) else value

    @classmethod
    def _reference_address(cls, row: pd.Series) -> str | None:
        direct_address = cls._reference_value(row, "Адрес", -1)
        if direct_address:
            return str(direct_address)

        parts = [
            cls._reference_value(row, "Город", 6),
            cls._reference_value(row, "Улица", 7),
            cls._reference_value(row, "Номер дома", 8),
        ]
        text_parts = [str(part) for part in parts if part not in (None, "")]
        return ", ".join(text_parts) if text_parts else None

    @staticmethod
    def _current_match_code(item: WasteObject | None) -> int | None:
        if item is None:
            return None
        return {
            "address_name_inn_plus": 3,
            "address_name_inn_minus": 2,
            "address_name_minus_inn_plus": 1,
            "address_plus": 0,
        }.get(item.contract_link_strategy)

    @staticmethod
    def _format_date(value) -> str | None:
        if value is None:
            return None
        return format_date_ru(value)

    @staticmethod
    def _autosize_columns(worksheet, dataframe: pd.DataFrame) -> None:
        for index, column in enumerate(dataframe.columns, start=1):
            values = [str(column)]
            values.extend("" if pd.isna(value) else str(value) for value in dataframe[column].tolist())
            max_length = max((len(value) for value in values), default=10)
            worksheet.column_dimensions[worksheet.cell(row=1, column=index).column_letter].width = min(max(max_length + 2, 12), 60)
