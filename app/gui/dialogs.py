from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from app.db import SessionLocal
from app.gui.clipboard import attach_edit_menu, make_copyable
from app.repositories.contract_row_repository import ContractRowRepository
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.services.contract_matching_service import CONTRACT_LINK_STATUS_LABELS, CONTRACT_LINK_STRATEGY_LABELS
from app.services.manual_data_service import ManualDataService
from app.utils.formatting import format_date_ru
from app.utils.normalization import split_normalized_inns


class BaseEditDialog(tk.Toplevel):
    def __init__(self, master, title: str, on_saved) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry("900x700")
        self.minsize(760, 540)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)
        self.on_saved = on_saved
        self.service = ManualDataService()

        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)

    @staticmethod
    def _add_labeled_entry(parent, row: int, label: str, value: Optional[str] = None, width: int = 32):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(0, 4))
        entry = ttk.Entry(parent, width=width)
        entry.grid(row=row, column=1, sticky="ew", pady=(0, 12), padx=(12, 0))
        if value not in (None, ""):
            entry.insert(0, str(value))
        attach_edit_menu(entry)
        return entry

    @staticmethod
    def _add_labeled_text(parent, row: int, label: str, value: Optional[str] = None, height: int = 4):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", pady=(0, 4))
        text = tk.Text(parent, height=height, wrap="word")
        text.grid(row=row, column=1, sticky="nsew", pady=(0, 12), padx=(12, 0))
        if value not in (None, ""):
            text.insert("1.0", str(value))
        attach_edit_menu(text)
        return text

    @staticmethod
    def _set_readonly_text(widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _show_error(self, exc: Exception) -> None:
        messagebox.showerror("Ошибка", str(exc), parent=self)

    def close_dialog(self) -> None:
        self.destroy()

    def _app_root(self):
        return self.master

    def _replace_with(self, dialog_class, entity_id: int) -> None:
        geometry = self.geometry()
        app_root = self._app_root()
        if hasattr(app_root, "show_dialog"):
            app_root.show_dialog(dialog_class, entity_id, geometry=geometry)
        else:
            return

    def _create_tree(self, parent, columns: tuple[str, ...], headings: tuple[str, ...], height: int = 8):
        frame = ttk.Frame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        tree.grid(row=0, column=0, sticky="nsew")
        for column, heading in zip(columns, headings, strict=True):
            tree.heading(column, text=heading)
            tree.column(column, anchor="w", width=180)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        return frame, tree

    @staticmethod
    def _wrap_value(value: object, width: int = 40) -> str:
        import textwrap

        text = str(value) if value not in (None, "") else "—"
        return textwrap.fill(text, width=width, break_long_words=False, break_on_hyphens=False)

    @staticmethod
    def _format_inn_display(value: Optional[str]) -> str:
        if value in (None, ""):
            return "—"
        return str(value).replace("|", "\n")

    @staticmethod
    def _format_contract_link_display(item) -> str:
        strategy = CONTRACT_LINK_STRATEGY_LABELS.get(item.contract_link_strategy or "")
        if strategy:
            return strategy

        status = CONTRACT_LINK_STATUS_LABELS.get(item.contract_link_status or "")
        if status:
            if item.contract_number and item.contract_link_status in {"unmatched", "review_required"}:
                return f"{status} (номер есть в основной базе)"
            return status

        if item.contract_number:
            return "Номер есть в основной базе"

        return "—"

    @staticmethod
    def _tree_insert(tree, iid: str, values: tuple[object, ...]) -> None:
        tree.insert("", "end", iid=iid, values=values)


class RealEstateEditDialog(BaseEditDialog):
    def __init__(self, master, real_estate_id: int, on_saved) -> None:
        super().__init__(master, "Редактирование объекта недвижимости", on_saved)
        self.real_estate_id = real_estate_id
        self._build()

    def _build(self) -> None:
        with SessionLocal() as db:
            item = RealEstateRepository.get_by_id(db, self.real_estate_id)
            if item is None:
                self.destroy()
                return

            form = ttk.LabelFrame(self.container, text="Данные объекта", padding=16)
            form.pack(fill="x")
            form.columnconfigure(1, weight=1)

            self.address_entry = self._add_labeled_entry(form, 0, "Полный адрес", item.address, width=70)
            self.district_entry = self._add_labeled_entry(form, 1, "Район", item.district)
            self.city_entry = self._add_labeled_entry(form, 2, "Город / населённый пункт", item.city)
            self.street_entry = self._add_labeled_entry(form, 3, "Улица", item.street)
            self.building_entry = self._add_labeled_entry(form, 4, "Дом / помещение", item.building)
            self.cadastral_entry = self._add_labeled_entry(form, 5, "Кадастровый номер", item.cadastral_number)
            self.area_entry = self._add_labeled_entry(form, 6, "Площадь", item.area)
            self.floors_entry = self._add_labeled_entry(form, 7, "Этажность", item.floors)
            self.purpose_entry = self._add_labeled_entry(form, 8, "Назначение", item.purpose, width=50)
            self.object_type_entry = self._add_labeled_entry(form, 9, "Тип объекта", item.object_type, width=50)

            related = ttk.LabelFrame(self.container, text="Связанные объекты отходов", padding=16)
            related.pack(fill="both", expand=True, pady=(16, 0))
            related.columnconfigure(0, weight=1)
            related.rowconfigure(0, weight=1)
            tree_frame, self.related_waste_tree = self._create_tree(
                related,
                columns=("name", "category", "inn"),
                headings=("Наименование", "Категория", "ИНН"),
                height=10,
            )
            tree_frame.grid(row=0, column=0, sticky="nsew")
            self.related_waste_tree.bind("<Double-1>", lambda _event: self._open_selected_waste_object())
            for waste in item.waste_objects:
                self.related_waste_tree.insert(
                    "",
                    "end",
                    iid=str(waste.id),
                    values=(
                        self._wrap_value(waste.name or "Без названия", width=28),
                        self._wrap_value(waste.category or "—", width=28),
                        self._format_inn_display(waste.inn),
                    ),
                )
            actions = ttk.Frame(related)
            actions.grid(row=1, column=0, sticky="e", pady=(12, 0))
            ttk.Button(actions, text="Открыть выбранный объект", command=self._open_selected_waste_object).pack(side="right")

        buttons = ttk.Frame(self.container)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Сохранить", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Закрыть", command=self.close_dialog).pack(side="right", padx=(0, 8))

    def _open_selected_waste_object(self) -> None:
        selected = self.related_waste_tree.selection()
        if not selected:
            messagebox.showinfo("Связанные объекты", "Выберите объект отходов для открытия.", parent=self)
            return
        self._replace_with(WasteObjectEditDialog, int(selected[0]))

    def _save(self) -> None:
        data = {
            "address": self.address_entry.get(),
            "district": self.district_entry.get(),
            "city": self.city_entry.get(),
            "street": self.street_entry.get(),
            "building": self.building_entry.get(),
            "cadastral_number": self.cadastral_entry.get(),
            "area": self.area_entry.get(),
            "floors": self.floors_entry.get(),
            "purpose": self.purpose_entry.get(),
            "object_type": self.object_type_entry.get(),
        }
        try:
            with SessionLocal() as db:
                item = RealEstateRepository.get_by_id(db, self.real_estate_id)
                if item is None:
                    raise ValueError("Объект недвижимости не найден.")
                self.service.update_real_estate(db, item, data)
                db.commit()
            self.on_saved()
            self.close_dialog()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)


class WasteObjectEditDialog(BaseEditDialog):
    def __init__(self, master, waste_object_id: int, on_saved) -> None:
        super().__init__(master, "Редактирование объекта отходов", on_saved)
        self.waste_object_id = waste_object_id
        self._build()

    def _build(self) -> None:
        with SessionLocal() as db:
            item = WasteObjectRepository.get_by_id(db, self.waste_object_id)
            if item is None:
                self.destroy()
                return

            top = ttk.Frame(self.container)
            top.pack(fill="both", expand=True)
            top.columnconfigure(0, weight=1)
            top.columnconfigure(1, weight=1)

            left = ttk.LabelFrame(top, text="Данные объекта отходов", padding=16)
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            left.columnconfigure(1, weight=1)

            self.name_entry = self._add_labeled_entry(left, 0, "Наименование", item.name, width=40)
            self.category_entry = self._add_labeled_entry(left, 1, "Категория", item.category, width=40)
            self.waste_type_entry = self._add_labeled_entry(left, 2, "Вид отходов", item.waste_type, width=40)
            self.volume_entry = self._add_labeled_entry(left, 3, "Объём", item.calculation_value)
            self.billing_entry = self._add_labeled_entry(left, 4, "Как начисляется", item.billing_method)
            self.contract_number_entry = self._add_labeled_entry(left, 5, "Номер договора", item.contract_number)
            self.contract_date_entry = self._add_labeled_entry(left, 6, "Дата договора", format_date_ru(item.contract_date))
            self.comment_text = self._add_labeled_text(left, 7, "Комментарий", item.comment, height=5)
            ttk.Label(left, text="Статус привязки").grid(row=8, column=0, sticky="w", pady=(0, 4))
            status_value = CONTRACT_LINK_STATUS_LABELS.get(item.contract_link_status or "", "—")
            status_label = ttk.Label(left, text=status_value, wraplength=340, justify="left")
            status_label.grid(row=8, column=1, sticky="w", pady=(0, 12), padx=(12, 0))
            make_copyable(status_label, text_getter=lambda value=status_value: value)

            ttk.Label(left, text="Алгоритм сопоставления").grid(row=9, column=0, sticky="w", pady=(0, 4))
            strategy_value = self._format_contract_link_display(item)
            strategy_label = ttk.Label(left, text=strategy_value, wraplength=340, justify="left")
            strategy_label.grid(row=9, column=1, sticky="w", pady=(0, 12), padx=(12, 0))
            make_copyable(strategy_label, text_getter=lambda value=strategy_value: value)

            left.rowconfigure(7, weight=1)

            right = ttk.LabelFrame(top, text="Связанное юридическое лицо", padding=16)
            right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
            right.columnconfigure(1, weight=1)

            legal = item.legal_entity
            self.inn_entry = self._add_labeled_entry(right, 0, "ИНН", item.inn)
            self.legal_name_entry = self._add_labeled_entry(right, 1, "Наименование", legal.name if legal else "", width=42)
            self.contact_entry = self._add_labeled_entry(right, 2, "Контактное лицо", legal.contact_person if legal else "", width=42)
            self.phone_entry = self._add_labeled_entry(right, 3, "Телефон", legal.phone if legal else "", width=42)
            self.email_entry = self._add_labeled_entry(right, 4, "Электронная почта", legal.email if legal else "", width=42)

            inn_links_row = ttk.Frame(right)
            inn_links_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
            ttk.Label(inn_links_row, text="Открыть по ИНН").pack(anchor="w")
            inn_button_frame = ttk.Frame(inn_links_row)
            inn_button_frame.pack(anchor="w", pady=(6, 0))
            for inn in split_normalized_inns(item.inn):
                entity = LegalEntityRepository.get_by_inn(db, inn)
                link = tk.Label(
                    inn_button_frame,
                    text=inn,
                    fg="#0d6efd" if entity else "#777777",
                    cursor="hand2" if entity else "arrow",
                )
                link.pack(side="left", padx=(0, 10), pady=(0, 4))
                make_copyable(link, text_getter=lambda inn_value=inn: inn_value)
                if entity is not None:
                    link.bind(
                        "<Button-1>",
                        lambda _event, entity_id=entity.id, inn_value=inn: self._open_legal_entity_by_inn(entity_id, inn_value),
                    )

            info = ttk.LabelFrame(self.container, text="Связанный объект недвижимости", padding=16)
            info.pack(fill="x", pady=(16, 0))
            address_label = ttk.Label(info, text=item.real_estate.address, wraplength=760, justify="left")
            address_label.pack(anchor="w")
            make_copyable(address_label, text_getter=lambda value=item.real_estate.address: value or "")
            info_actions = ttk.Frame(info)
            info_actions.pack(anchor="w", pady=(12, 0))
            ttk.Button(
                info_actions,
                text="Открыть объект недвижимости",
                command=lambda: self._open_real_estate(item.real_estate.id),
            ).pack(side="left")
            ttk.Button(
                info_actions,
                text="Открыть юридическое лицо",
                command=lambda: self._open_legal_entity(item.legal_entity.id if item.legal_entity else None),
                state="normal" if item.legal_entity else "disabled",
            ).pack(side="left", padx=(8, 0))

        buttons = ttk.Frame(self.container)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Сохранить", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Закрыть", command=self.close_dialog).pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        data = {
            "name": self.name_entry.get(),
            "category": self.category_entry.get(),
            "waste_type": self.waste_type_entry.get(),
            "calculation_value": self.volume_entry.get(),
            "billing_method": self.billing_entry.get(),
            "inn": self.inn_entry.get(),
            "legal_entity_name": self.legal_name_entry.get(),
            "contact_person": self.contact_entry.get(),
            "phone": self.phone_entry.get(),
            "email": self.email_entry.get(),
            "contract_number": self.contract_number_entry.get(),
            "contract_date": self.contract_date_entry.get(),
            "comment": self.comment_text.get("1.0", "end").strip(),
        }
        try:
            with SessionLocal() as db:
                item = WasteObjectRepository.get_by_id(db, self.waste_object_id)
                if item is None:
                    raise ValueError("Объект отходов не найден.")
                self.service.update_waste_object(db, item, data)
                db.commit()
            self.on_saved()
            self.close_dialog()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_real_estate(self, real_estate_id: int) -> None:
        self._replace_with(RealEstateEditDialog, real_estate_id)

    def _open_legal_entity(self, legal_entity_id: Optional[int]) -> None:
        if legal_entity_id is None:
            messagebox.showinfo("Юридическое лицо", "Связанное юридическое лицо не найдено.", parent=self)
            return
        self._replace_with(LegalEntityEditDialog, legal_entity_id)

    def _open_legal_entity_by_inn(self, legal_entity_id: Optional[int], inn: str) -> None:
        if legal_entity_id is None:
            messagebox.showinfo("Юридическое лицо", f"Юридическое лицо с ИНН {inn} не найдено.", parent=self)
            return
        self._replace_with(LegalEntityEditDialog, legal_entity_id)


class LegalEntityEditDialog(BaseEditDialog):
    def __init__(self, master, legal_entity_id: int, on_saved) -> None:
        super().__init__(master, "Редактирование юридического лица", on_saved)
        self.legal_entity_id = legal_entity_id
        self._build()

    def _build(self) -> None:
        with SessionLocal() as db:
            item = LegalEntityRepository.get_by_id(db, self.legal_entity_id)
            if item is None:
                self.destroy()
                return

            form = ttk.LabelFrame(self.container, text="Данные юридического лица", padding=16)
            form.pack(fill="x")
            form.columnconfigure(1, weight=1)

            self.inn_entry = self._add_labeled_entry(form, 0, "ИНН", item.inn)
            self.name_entry = self._add_labeled_entry(form, 1, "Наименование", item.name, width=56)
            self.contact_entry = self._add_labeled_entry(form, 2, "Контактное лицо", item.contact_person, width=56)
            self.phone_entry = self._add_labeled_entry(form, 3, "Телефон", item.phone, width=56)
            self.email_entry = self._add_labeled_entry(form, 4, "Электронная почта", item.email, width=56)

            related = ttk.LabelFrame(self.container, text="Связанные объекты отходов", padding=16)
            related.pack(fill="both", expand=True, pady=(16, 0))
            related.columnconfigure(0, weight=1)
            related.rowconfigure(0, weight=1)
            tree_frame, self.related_waste_tree = self._create_tree(
                related,
                columns=("name", "category", "address"),
                headings=("Наименование", "Категория", "Адрес"),
                height=12,
            )
            tree_frame.grid(row=0, column=0, sticky="nsew")
            self.related_waste_tree.bind("<Double-1>", lambda _event: self._open_selected_waste_object())
            related_waste_objects = LegalEntityRepository.list_related_waste_objects(db, item.id)
            for waste in related_waste_objects:
                self.related_waste_tree.insert(
                    "",
                    "end",
                    iid=str(waste.id),
                    values=(
                        self._wrap_value(waste.name or "Без названия", width=28),
                        self._wrap_value(waste.category or "—", width=28),
                        self._wrap_value(waste.real_estate.address, width=44),
                    ),
                )
            actions = ttk.Frame(related)
            actions.grid(row=1, column=0, sticky="e", pady=(12, 0))
            ttk.Button(actions, text="Открыть выбранный объект", command=self._open_selected_waste_object).pack(side="right")

        buttons = ttk.Frame(self.container)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Сохранить", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Закрыть", command=self.close_dialog).pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        data = {
            "inn": self.inn_entry.get(),
            "name": self.name_entry.get(),
            "contact_person": self.contact_entry.get(),
            "phone": self.phone_entry.get(),
            "email": self.email_entry.get(),
        }
        try:
            with SessionLocal() as db:
                item = LegalEntityRepository.get_by_id(db, self.legal_entity_id)
                if item is None:
                    raise ValueError("Юридическое лицо не найдено.")
                self.service.update_legal_entity(db, item, data)
                db.commit()
            self.on_saved()
            self.close_dialog()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_selected_waste_object(self) -> None:
        selected = self.related_waste_tree.selection()
        if not selected:
            messagebox.showinfo("Связанные объекты", "Выберите объект отходов для открытия.", parent=self)
            return
        self._replace_with(WasteObjectEditDialog, int(selected[0]))


class ContractRowEditDialog(BaseEditDialog):
    def __init__(self, master, contract_row_id: int, on_saved) -> None:
        super().__init__(master, "Ручная привязка договора", on_saved)
        self.geometry("1480x860")
        self.minsize(1240, 760)
        self.contract_row_id = contract_row_id
        self.candidate_filter_vars = {
            "name": tk.StringVar(),
            "address": tk.StringVar(),
            "inn": tk.StringVar(),
        }
        self.candidate_count_label: ttk.Label | None = None
        self.candidate_tree = None
        self._build()

    def _build(self) -> None:
        with SessionLocal() as db:
            contract_row = ContractRowRepository.get_by_id(db, self.contract_row_id)
            if contract_row is None:
                self.destroy()
                return

            top = ttk.Frame(self.container)
            top.pack(fill="both", expand=True)
            top.columnconfigure(0, weight=1)
            top.columnconfigure(1, weight=1)
            top.rowconfigure(0, weight=1)

            left = ttk.LabelFrame(top, text="Строка договора", padding=16)
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            left.columnconfigure(0, weight=1)
            left.columnconfigure(1, weight=1)

            left_col = ttk.Frame(left)
            left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            left_col.columnconfigure(1, weight=1)
            right_col = ttk.Frame(left)
            right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
            right_col.columnconfigure(1, weight=1)

            self.contract_number_entry = self._add_labeled_entry(left_col, 0, "Номер договора", contract_row.contract_number, width=28)
            self.contract_date_entry = self._add_labeled_entry(left_col, 1, "Дата договора", format_date_ru(contract_row.contract_date), width=28)
            self.legal_entity_name_entry = self._add_labeled_entry(left_col, 2, "Потребитель", contract_row.legal_entity_name, width=42)
            self.waste_object_name_entry = self._add_labeled_entry(left_col, 3, "Наименование ИОО", contract_row.waste_object_name, width=42)
            self.inn_entry = self._add_labeled_entry(left_col, 4, "ИНН", contract_row.inn, width=28)
            self.address_entry = self._add_labeled_entry(left_col, 5, "Адрес", contract_row.address, width=42)
            self.locality_entry = self._add_labeled_entry(right_col, 0, "Населённый пункт", contract_row.locality, width=32)
            self.street_entry = self._add_labeled_entry(right_col, 1, "Улица", contract_row.street, width=32)
            self.building_entry = self._add_labeled_entry(right_col, 2, "Дом", contract_row.building, width=20)
            self.room_entry = self._add_labeled_entry(right_col, 3, "Помещение", contract_row.room, width=20)
            self.volume_entry = self._add_labeled_entry(right_col, 4, "Объём", contract_row.volume, width=20)
            self.quantity_entry = self._add_labeled_entry(right_col, 5, "Количество", contract_row.quantity, width=20)
            self.frequency_entry = self._add_labeled_entry(right_col, 6, "Периодичность", contract_row.pickup_frequency, width=32)
            self.contact_entry = self._add_labeled_entry(right_col, 7, "Контакт", contract_row.contact_person, width=32)
            self.start_date_entry = self._add_labeled_entry(right_col, 8, "Дата начала действия", format_date_ru(contract_row.contract_start_date), width=20)
            self.comment_text = self._add_labeled_text(left, 1, "Комментарий", contract_row.comment, height=4)
            left.rowconfigure(1, weight=1)

            status_frame = ttk.Frame(left)
            status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
            status_text = CONTRACT_LINK_STATUS_LABELS.get(contract_row.contract_link_status or "", "—")
            ttk.Label(status_frame, text=f"Статус: {status_text}").pack(anchor="w")

            right = ttk.LabelFrame(top, text="Кандидаты из 2GIS", padding=16)
            right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
            right.columnconfigure(0, weight=1)
            right.rowconfigure(2, weight=1)

            filters = ttk.Frame(right)
            filters.grid(row=0, column=0, sticky="ew")
            ttk.Label(filters, text="Наименование").grid(row=0, column=0, sticky="w")
            name_entry = ttk.Entry(filters, textvariable=self.candidate_filter_vars["name"], width=28)
            name_entry.grid(row=0, column=1, sticky="w", padx=(6, 16))
            attach_edit_menu(name_entry)
            ttk.Label(filters, text="Адрес").grid(row=0, column=2, sticky="w")
            address_entry = ttk.Entry(filters, textvariable=self.candidate_filter_vars["address"], width=34)
            address_entry.grid(row=0, column=3, sticky="w", padx=(6, 16))
            attach_edit_menu(address_entry)
            ttk.Label(filters, text="ИНН").grid(row=0, column=4, sticky="w")
            inn_entry = ttk.Entry(filters, textvariable=self.candidate_filter_vars["inn"], width=20)
            inn_entry.grid(row=0, column=5, sticky="w", padx=(6, 0))
            attach_edit_menu(inn_entry)

            if contract_row.waste_object_name:
                self.candidate_filter_vars["name"].set(contract_row.waste_object_name)
            if contract_row.address:
                self.candidate_filter_vars["address"].set(contract_row.address)
            if contract_row.inn:
                self.candidate_filter_vars["inn"].set(contract_row.inn)

            filter_actions = ttk.Frame(right)
            filter_actions.grid(row=1, column=0, sticky="ew", pady=(10, 10))
            ttk.Button(filter_actions, text="Найти", command=self._refresh_candidates).pack(side="left")
            ttk.Button(filter_actions, text="Сбросить", command=self._reset_candidate_filters).pack(side="left", padx=(8, 0))
            ttk.Button(filter_actions, text="Открыть объект 2GIS", command=self._open_selected_candidate).pack(side="right")
            ttk.Button(filter_actions, text="Привязать к выбранному объекту", command=self._bind_selected_candidate).pack(side="right", padx=(0, 8))

            tree_frame, self.candidate_tree = self._create_tree(
                right,
                columns=("name", "category", "address", "inn", "contract"),
                headings=("Наименование", "Категория", "Адрес", "ИНН", "Договор"),
                height=14,
            )
            tree_frame.grid(row=2, column=0, sticky="nsew")
            self.candidate_tree.bind("<Double-1>", lambda _event: self._open_selected_candidate())
            self.candidate_count_label = ttk.Label(right, text="Найдено кандидатов: 0")
            self.candidate_count_label.grid(row=3, column=0, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(self.container)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Сохранить изменения договора", command=self._save_contract_row).pack(side="right")
        ttk.Button(buttons, text="Закрыть", command=self.close_dialog).pack(side="right", padx=(0, 8))
        self._refresh_candidates()

    def _contract_row_form_data(self) -> dict[str, object]:
        return {
            "contract_number": self.contract_number_entry.get(),
            "contract_date": self.contract_date_entry.get(),
            "legal_entity_name": self.legal_entity_name_entry.get(),
            "waste_object_name": self.waste_object_name_entry.get(),
            "inn": self.inn_entry.get(),
            "address": self.address_entry.get(),
            "locality": self.locality_entry.get(),
            "street": self.street_entry.get(),
            "building": self.building_entry.get(),
            "room": self.room_entry.get(),
            "volume": self.volume_entry.get(),
            "quantity": self.quantity_entry.get(),
            "pickup_frequency": self.frequency_entry.get(),
            "contact_person": self.contact_entry.get(),
            "contract_start_date": self.start_date_entry.get(),
            "comment": self.comment_text.get("1.0", "end").strip(),
        }

    def _save_contract_row(self) -> None:
        try:
            with SessionLocal() as db:
                contract_row = ContractRowRepository.get_by_id(db, self.contract_row_id)
                if contract_row is None:
                    raise ValueError("Строка договора не найдена.")
                self.service.update_contract_row(db, contract_row, self._contract_row_form_data())
                db.commit()
            self.on_saved()
            self.close_dialog()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _refresh_candidates(self) -> None:
        if self.candidate_tree is None:
            return
        for child in self.candidate_tree.get_children():
            self.candidate_tree.delete(child)

        with SessionLocal() as db:
            linked_ids = ContractRowRepository.linked_waste_object_ids(db, exclude_contract_row_id=self.contract_row_id)
            rows = WasteObjectRepository.list(
                db,
                {
                    "name": self.candidate_filter_vars["name"].get(),
                    "address": self.candidate_filter_vars["address"].get(),
                    "inn": self.candidate_filter_vars["inn"].get(),
                },
            )

        rows = [item for item in rows if item.id not in linked_ids][:150]
        for item in rows:
            self._tree_insert(
                self.candidate_tree,
                str(item.id),
                (
                    self._wrap_value(item.name or "—", width=28),
                    self._wrap_value(item.category or "—", width=24),
                    self._wrap_value(item.real_estate.address, width=42),
                    self._format_inn_display(item.inn),
                    item.contract_number or "—",
                ),
            )
        if self.candidate_count_label is not None:
            self.candidate_count_label.configure(text=f"Найдено кандидатов: {len(rows)}")

    def _reset_candidate_filters(self) -> None:
        for variable in self.candidate_filter_vars.values():
            variable.set("")
        self._refresh_candidates()

    def _open_selected_candidate(self) -> None:
        if self.candidate_tree is None:
            return
        selected = self.candidate_tree.selection()
        if not selected:
            messagebox.showinfo("Кандидаты 2GIS", "Выберите объект для открытия.", parent=self)
            return
        self._replace_with(WasteObjectEditDialog, int(selected[0]))

    def _bind_selected_candidate(self) -> None:
        if self.candidate_tree is None:
            return
        selected = self.candidate_tree.selection()
        if not selected:
            messagebox.showinfo("Кандидаты 2GIS", "Выберите объект для привязки.", parent=self)
            return
        try:
            with SessionLocal() as db:
                contract_row = ContractRowRepository.get_by_id(db, self.contract_row_id)
                waste_object = WasteObjectRepository.get_by_id(db, int(selected[0]))
                if contract_row is None:
                    raise ValueError("Строка договора не найдена.")
                if waste_object is None:
                    raise ValueError("Объект 2GIS не найден.")
                self.service.update_contract_row(db, contract_row, self._contract_row_form_data())
                self.service.bind_contract_row_to_waste_object(db, contract_row, waste_object)
                db.commit()
            self.on_saved()
            self.close_dialog()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
