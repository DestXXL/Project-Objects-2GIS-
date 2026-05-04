from __future__ import annotations

import queue
from pathlib import Path
import threading
import tkinter as tk
import textwrap
from tkinter import filedialog, messagebox, simpledialog, ttk

from app.bootstrap import ensure_database_ready
from app import db as database
from app.db import SessionLocal, configure_database
from app.repositories.contract_row_repository import ContractRowRepository
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.schemas.dashboard import DashboardStats
from app.services.contract_matching_service import CONTRACT_LINK_STATUS_LABELS, CONTRACT_LINK_STRATEGY_LABELS
from app.services.dashboard_service import DashboardService
from app.services.data_reset_service import DataResetService
from app.services.export_service import ExportService
from app.services.file_parser import FileParserService
from app.services.import_service import ImportService
from app.services.project_service import ProjectInfo, ProjectService
from app.gui.clipboard import attach_edit_menu, install_clipboard_support, make_copyable
from app.gui.dialogs import ContractRowEditDialog, LegalEntityEditDialog, RealEstateEditDialog, WasteObjectEditDialog


def run_desktop_app() -> None:
    project_service = ProjectService()
    current_project = project_service.get_current_project()
    configure_database(current_project.database_path)
    ensure_database_ready(current_project.database_path)
    app = DesktopApp(project_service=project_service, current_project=current_project)
    app.mainloop()


class DesktopApp(tk.Tk):
    def __init__(self, project_service: ProjectService, current_project: ProjectInfo) -> None:
        super().__init__()
        self.title("Реестр объектов отходов")
        self.geometry("1440x920")
        self.minsize(1180, 760)
        self.project_service = project_service
        self.current_project = current_project
        self.project_var = tk.StringVar()
        self.projects_by_label: dict[str, ProjectInfo] = {}
        self.project_combo: ttk.Combobox | None = None
        self.database_label: ttk.Label | None = None

        self.dashboard_service = DashboardService()
        self.file_parser = FileParserService()
        self.import_service = ImportService()
        self.data_reset_service = DataResetService()
        self.export_service = ExportService()

        self._configure_style()
        install_clipboard_support(self)
        self._build_header()
        self._build_tabs()
        self.refresh_all()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("Arial", 20, "bold"))
        style.configure("SubHeader.TLabel", font=("Arial", 10))
        style.configure("MetricValue.TLabel", font=("Arial", 24, "bold"))
        style.configure("MetricLabel.TLabel", foreground="#555555")

    def _build_header(self) -> None:
        header = ttk.Frame(self, padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Учёт недвижимости", style="Header.TLabel").pack(anchor="w")
        project_row = ttk.Frame(header)
        project_row.pack(fill="x", pady=(8, 0))
        ttk.Label(project_row, text="Проект").pack(side="left")
        self.project_combo = ttk.Combobox(project_row, textvariable=self.project_var, state="readonly", width=42)
        self.project_combo.pack(side="left", padx=(8, 8))
        self.project_combo.bind("<<ComboboxSelected>>", self._on_project_selected)
        ttk.Button(project_row, text="Новый проект", command=self._create_project).pack(side="left")

        self.database_label = ttk.Label(header, text="", style="SubHeader.TLabel")
        self.database_label.pack(anchor="w", pady=(4, 0))
        self._refresh_project_selector()

    def _refresh_project_selector(self) -> None:
        projects = self.project_service.list_projects()
        self.projects_by_label = {self._project_label(project): project for project in projects}
        labels = list(self.projects_by_label)
        if self.project_combo is not None:
            self.project_combo.configure(values=labels)
        self.project_var.set(self._project_label(self.current_project))
        self._update_database_label()

    def _update_database_label(self) -> None:
        if self.database_label is not None:
            self.database_label.configure(text=f"База данных: {database.current_database_path}")

    @staticmethod
    def _project_label(project: ProjectInfo) -> str:
        return project.name

    def _on_project_selected(self, _event=None) -> None:
        selected = self.projects_by_label.get(self.project_var.get())
        if selected is None or selected.id == self.current_project.id:
            return
        self._switch_project(selected.id)

    def _create_project(self) -> None:
        name = simpledialog.askstring("Новый проект", "Введите название проекта:", parent=self)
        if name is None:
            return
        try:
            project = self.project_service.create_project(name)
            self._switch_project(project.id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Новый проект", str(exc), parent=self)

    def _switch_project(self, project_id: str) -> None:
        if hasattr(self, "import_tab") and self.import_tab.is_busy():
            messagebox.showwarning("Переключение проекта", "Дождитесь завершения импорта.", parent=self)
            self._refresh_project_selector()
            return

        try:
            project = self.project_service.set_current_project(project_id)
            configure_database(project.database_path)
            ensure_database_ready(project.database_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Переключение проекта", str(exc), parent=self)
            self._refresh_project_selector()
            return

        self.current_project = project
        self._refresh_project_selector()
        self.refresh_all()

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.dashboard_tab = DashboardTab(self.notebook, self)
        self.import_tab = ImportTab(self.notebook, self)
        self.contract_rows_tab = ContractRowsTab(self.notebook, self)
        self.real_estate_tab = RealEstateTab(self.notebook, self)
        self.waste_object_tab = WasteObjectTab(self.notebook, self)
        self.legal_entity_tab = LegalEntityTab(self.notebook, self)

        self.notebook.add(self.dashboard_tab, text="Сводка")
        self.notebook.add(self.import_tab, text="Импорт")
        self.notebook.add(self.contract_rows_tab, text="Договоры к разбору")
        self.notebook.add(self.real_estate_tab, text="Недвижимость")
        self.notebook.add(self.waste_object_tab, text="Объекты отходов")
        self.notebook.add(self.legal_entity_tab, text="Юрлица")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def refresh_all(self) -> None:
        for tab in (
            self.dashboard_tab,
            self.contract_rows_tab,
            self.real_estate_tab,
            self.waste_object_tab,
            self.legal_entity_tab,
        ):
            tab.mark_dirty()
        self._refresh_selected_tab(force=True)

    def show_dialog(self, dialog_class, entity_id: int, geometry: str | None = None):
        dialog = dialog_class(self, entity_id, self.refresh_all)
        if geometry:
            dialog.geometry(geometry)
        return dialog

    def _on_tab_changed(self, _event=None) -> None:
        self._refresh_selected_tab()

    def _refresh_selected_tab(self, force: bool = False) -> None:
        selected = self.notebook.nametowidget(self.notebook.select())
        if hasattr(selected, "ensure_fresh"):
            selected.ensure_fresh(force=force)


def format_contract_link_display(item) -> str:
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


class DashboardTab(ttk.Frame):
    def __init__(self, master, app: DesktopApp) -> None:
        super().__init__(master, padding=18)
        self.app = app
        self._loaded = False
        self._dirty = True

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Обновить", command=self.refresh).pack(side="right")

        metrics = ttk.Frame(self)
        metrics.pack(fill="x", pady=(16, 0))
        for column in range(3):
            metrics.columnconfigure(column, weight=1)

        self.metric_frames = {}
        for index, title in enumerate(("Объекты недвижимости", "Объекты отходов", "Юридические лица")):
            card = ttk.LabelFrame(metrics, text=title, padding=16)
            card.grid(row=0, column=index, sticky="nsew", padx=8)
            value_label = ttk.Label(card, text="0", style="MetricValue.TLabel")
            value_label.pack(anchor="w")
            self.metric_frames[title] = value_label



    def refresh(self) -> None:
        with SessionLocal() as db:
            stats: DashboardStats = self.app.dashboard_service.get_stats(db)
        self.metric_frames["Объекты недвижимости"].configure(text=str(stats.real_estates))
        self.metric_frames["Объекты отходов"].configure(text=str(stats.waste_objects))
        self.metric_frames["Юридические лица"].configure(text=str(stats.legal_entities))
        self._loaded = True
        self._dirty = False

    def ensure_fresh(self, force: bool = False) -> None:
        if force or self._dirty or not self._loaded:
            self.refresh()

    def mark_dirty(self) -> None:
        self._dirty = True


class ImportTab(ttk.Frame):
    def __init__(self, master, app: DesktopApp) -> None:
        super().__init__(master, padding=18)
        self.app = app
        self.main_file_var = tk.StringVar()
        self.contract_file_var = tk.StringVar()
        self._worker_thread: threading.Thread | None = None
        self._worker_queue: queue.Queue | None = None
        self._progress_dialog: ImportProgressDialog | None = None

        form = ttk.LabelFrame(self, text="Импорт файлов", padding=16)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Основной файл").grid(row=0, column=0, sticky="w")
        self.main_entry = ttk.Entry(form, textvariable=self.main_file_var)
        self.main_entry.grid(row=0, column=1, sticky="ew", padx=12)
        attach_edit_menu(self.main_entry)
        self.main_pick_button = ttk.Button(form, text="Выбрать", command=self._pick_main_file)
        self.main_pick_button.grid(row=0, column=2, sticky="e")

        ttk.Label(form, text="Файл договоров").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.contract_entry = ttk.Entry(form, textvariable=self.contract_file_var)
        self.contract_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=(12, 0))
        attach_edit_menu(self.contract_entry)
        self.contract_pick_button = ttk.Button(form, text="Выбрать", command=self._pick_contract_file)
        self.contract_pick_button.grid(row=1, column=2, sticky="e", pady=(12, 0))

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        self.import_button = ttk.Button(actions, text="Импортировать", command=self._import_files)
        self.import_button.pack(side="left")
        self.reset_button = ttk.Button(actions, text="Очистить текущие данные", command=self._reset_data)
        self.reset_button.pack(side="left", padx=(8, 0))
        self.export_button = ttk.Button(actions, text="Выгрузить в Excel", command=self._export_excel)
        self.export_button.pack(side="left", padx=(8, 0))

    def is_busy(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _pick_main_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите основной файл",
            filetypes=[("Excel/CSV", "*.xlsx *.csv"), ("Все файлы", "*.*")],
        )
        if path:
            self.main_file_var.set(path)

    def _pick_contract_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите файл договоров",
            filetypes=[("Excel/CSV", "*.xlsx *.csv"), ("Все файлы", "*.*")],
        )
        if path:
            self.contract_file_var.set(path)

    def _import_files(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        main_path = Path(self.main_file_var.get().strip()) if self.main_file_var.get().strip() else None
        contract_path = Path(self.contract_file_var.get().strip()) if self.contract_file_var.get().strip() else None
        if main_path is None or not main_path.exists():
            messagebox.showwarning("Импорт", "Выберите основной файл для импорта.", parent=self)
            return

        self._set_import_controls_enabled(False)
        self._worker_queue = queue.Queue()
        self._progress_dialog = ImportProgressDialog(self)
        self._progress_dialog.update_progress({"message": "Подготовка импорта", "current": None, "total": None})
        self._worker_thread = threading.Thread(
            target=self._run_import_worker,
            args=(main_path, contract_path),
            daemon=True,
        )
        self._worker_thread.start()
        self.after(100, self._poll_import_queue)

    def _run_import_worker(self, main_path: Path, contract_path: Path | None) -> None:
        assert self._worker_queue is not None
        try:
            self._worker_queue.put({"type": "progress", "payload": {"message": "Чтение основного файла"}})
            dataframe = self.app.file_parser.read_dataframe(main_path.name, main_path.read_bytes())

            contract_dataframe = None
            if contract_path:
                if not contract_path.exists():
                    raise ValueError("Файл договоров не найден.")
                self._worker_queue.put({"type": "progress", "payload": {"message": "Чтение файла договоров"}})
                contract_dataframe = self.app.file_parser.read_dataframe(contract_path.name, contract_path.read_bytes())

            with SessionLocal() as db:
                result = self.app.import_service.import_dataframe(
                    db,
                    dataframe,
                    contract_dataframe=contract_dataframe,
                    progress_callback=lambda payload: self._worker_queue.put({"type": "progress", "payload": payload}),
                )

            self._worker_queue.put({"type": "success", "payload": result})
        except Exception as exc:  # noqa: BLE001
            self._worker_queue.put({"type": "error", "payload": str(exc)})

    def _poll_import_queue(self) -> None:
        if self._worker_queue is None:
            return

        finished = False
        while True:
            try:
                event = self._worker_queue.get_nowait()
            except queue.Empty:
                break

            event_type = event.get("type")
            payload = event.get("payload")
            if event_type == "progress":
                if self._progress_dialog is not None:
                    self._progress_dialog.update_progress(payload)
            elif event_type == "success":
                finished = True
                self._finish_import(success=True, result=payload)
            elif event_type == "error":
                finished = True
                self._finish_import(success=False, error_message=payload)

        if not finished and self._worker_thread is not None and self._worker_thread.is_alive():
            self.after(100, self._poll_import_queue)
        elif not finished:
            self._finish_import(success=False, error_message="Импорт завершился некорректно.")

    def _finish_import(self, success: bool, result=None, error_message: str | None = None) -> None:
        self._set_import_controls_enabled(True)
        if self._progress_dialog is not None:
            self._progress_dialog.close_dialog()
            self._progress_dialog = None
        self._worker_thread = None
        self._worker_queue = None

        if success:
            self.app.refresh_all()
            if result is not None:
                messagebox.showinfo(
                    "Импорт завершён",
                    (
                        f"Обработано строк: {result.processed_rows}\n"
                        f"Создано объектов недвижимости: {result.real_estates_created}\n"
                        f"Создано объектов отходов: {result.waste_objects_created}\n"
                        f"Создано юридических лиц: {result.legal_entities_created}\n"
                        f"Строк договоров нашли пару в 2GIS: {result.contract_rows_matched}\n"
                        f"Строк 2GIS с привязанным договором: {result.gis_rows_linked_to_contract}"
                    ),
                    parent=self,
                )
            return

        messagebox.showerror("Ошибка импорта", error_message or "Неизвестная ошибка импорта.", parent=self)

    def _set_import_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (
            self.main_entry,
            self.contract_entry,
            self.main_pick_button,
            self.contract_pick_button,
            self.import_button,
            self.reset_button,
            self.export_button,
        ):
            widget.configure(state=state)

    def _reset_data(self) -> None:
        confirmed = messagebox.askyesno(
            "Очистка данных",
            "Удалить все ранее импортированные данные? Это действие нельзя отменить.",
            parent=self,
        )
        if not confirmed:
            return

        try:
            with SessionLocal() as db:
                self.app.data_reset_service.reset_all_imported_data(db)
            self.app.refresh_all()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ошибка очистки", str(exc), parent=self)

    def _export_excel(self) -> None:
        destination = filedialog.asksaveasfilename(
            title="Сохранить объединённую базу",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("Все файлы", "*.*")],
            initialfile="объединенная_база.xlsx",
        )
        if not destination:
            return

        try:
            with SessionLocal() as db:
                output_path = self.app.export_service.export_to_excel(db, destination)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ошибка выгрузки", str(exc), parent=self)
            return

        messagebox.showinfo(
            "Выгрузка завершена",
            f"Объединённая база сохранена в файл:\n{output_path}",
            parent=self,
        )


class ImportProgressDialog(tk.Toplevel):
    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("Импорт данных")
        self.geometry("520x170")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        container = ttk.Frame(self, padding=18)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Файлы загружаются, пожалуйста подождите.", font=("Arial", 12, "bold")).pack(
            anchor="w"
        )
        self.message_label = ttk.Label(container, text="Подготовка импорта", wraplength=470, justify="left")
        self.message_label.pack(anchor="w", pady=(14, 8))
        self.progress = ttk.Progressbar(container, mode="indeterminate", length=470)
        self.progress.pack(anchor="w", fill="x")
        self.progress.start(10)
        self.percent_label = ttk.Label(container, text="")
        self.percent_label.pack(anchor="w", pady=(10, 0))

    def update_progress(self, payload: dict) -> None:
        message = payload.get("message") or "Импорт выполняется"
        current = payload.get("current")
        total = payload.get("total")

        self.message_label.configure(text=message)
        if isinstance(current, int) and isinstance(total, int) and total > 0:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=total, value=min(current, total))
            percent = int((min(current, total) / total) * 100)
            self.percent_label.configure(text=f"{current} из {total} ({percent}%)")
        else:
            if str(self.progress.cget("mode")) != "indeterminate":
                self.progress.configure(mode="indeterminate")
                self.progress.start(10)
            self.percent_label.configure(text="")

    def close_dialog(self) -> None:
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.destroy()


class BaseTreeTab(ttk.Frame):
    columns: tuple[str, ...] = ()
    headings: tuple[str, ...] = ()
    filter_specs: tuple[tuple[str, str, int], ...] = ()
    filter_check_specs: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = ()

    def __init__(self, master, app: DesktopApp, title: str) -> None:
        super().__init__(master, padding=18)
        self.app = app
        self.title = title
        self.filter_vars = {key: tk.StringVar() for key, _label, _width in self.filter_specs}
        self.filter_check_vars = {
            key: {value: tk.BooleanVar(value=False) for value, _label in options}
            for key, _label, options in self.filter_check_specs
        }
        self.selected_item_id: int | None = None
        self.row_frames: dict[int, tuple[tk.Frame, list[tk.Label]]] = {}
        self.page_size = 150
        self.current_page = 0
        self._rows_data: list[tuple[int, tuple[object, ...]]] = []
        self._loaded = False
        self._dirty = True
        self._total_rows = 0
        self._content_width = sum(self._column_width(column) for column in self.columns)
        self._data_cache_key: tuple[tuple[str, str], ...] | None = None
        self._data_cache_rows = None
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        filter_frame = ttk.Frame(toolbar)
        filter_frame.pack(side="left", fill="x", expand=True)
        for index, (key, label, width) in enumerate(self.filter_specs):
            row = index // 3
            column = (index % 3) * 2
            ttk.Label(filter_frame, text=label).grid(row=row, column=column, sticky="w", pady=(0, 6))
            entry = ttk.Entry(filter_frame, textvariable=self.filter_vars[key], width=width)
            entry.grid(row=row, column=column + 1, sticky="w", padx=(6, 18), pady=(0, 6))
            entry.bind("<Return>", lambda _event: self._refresh_from_first_page())
            attach_edit_menu(entry)
        check_start_row = (len(self.filter_specs) + 2) // 3
        for index, (key, label, options) in enumerate(self.filter_check_specs):
            row = check_start_row + index
            ttk.Label(filter_frame, text=label).grid(row=row, column=0, sticky="w", pady=(0, 6))
            checks = ttk.Frame(filter_frame)
            checks.grid(row=row, column=1, columnspan=5, sticky="w", padx=(6, 18), pady=(0, 6))
            for value, option_label in options:
                ttk.Checkbutton(
                    checks,
                    text=option_label,
                    variable=self.filter_check_vars[key][value],
                    command=self._refresh_from_first_page,
                ).pack(side="left", padx=(0, 12))
        ttk.Button(toolbar, text="Открыть / изменить", command=self.open_selected).pack(side="right")
        ttk.Button(toolbar, text="Обновить", command=self._force_refresh).pack(side="right", padx=(0, 8))
        ttk.Button(toolbar, text="Сброс", command=self._reset_search).pack(side="right", padx=(0, 8))
        ttk.Button(toolbar, text="Найти", command=self._refresh_from_first_page).pack(side="right", padx=(0, 8))

        summary = ttk.Frame(self)
        summary.pack(fill="x", pady=(8, 0))
        self.result_count_label = ttk.Label(summary, text="Найдено записей: 0")
        self.result_count_label.pack(side="left")
        pagination = ttk.Frame(summary)
        pagination.pack(side="right")
        self.prev_page_button = ttk.Button(pagination, text="Назад", command=self._prev_page)
        self.prev_page_button.pack(side="left")
        self.page_label = ttk.Label(pagination, text="Страница 1 из 1")
        self.page_label.pack(side="left", padx=10)
        self.next_page_button = ttk.Button(pagination, text="Вперёд", command=self._next_page)
        self.next_page_button.pack(side="left")

        header_container = ttk.Frame(self)
        header_container.pack(fill="x", pady=(16, 0))
        self.header_canvas = tk.Canvas(
            header_container,
            highlightthickness=0,
            bg="#eef3fb",
            height=44,
        )
        self.header_canvas.pack(fill="x", expand=True)
        self.header_frame = tk.Frame(self.header_canvas, bg="#eef3fb", bd=1, relief="solid")
        self.header_window = self.header_canvas.create_window((0, 0), window=self.header_frame, anchor="nw")
        for index, (column, heading) in enumerate(zip(self.columns, self.headings, strict=True)):
            self.header_frame.grid_columnconfigure(index, minsize=self._column_width(column), weight=self._column_weight(column))
            label = tk.Label(
                self.header_frame,
                text=heading,
                font=("Arial", 11, "bold"),
                bg="#eef3fb",
                fg="#1f2937",
                anchor="w",
                justify="left",
                padx=10,
                pady=8,
                wraplength=max(self._column_width(column) - 24, 40),
            )
            label.grid(row=0, column=index, sticky="nsew")
            make_copyable(label)
        self.header_frame.bind("<Configure>", self._update_header_scrollregion)
        self.header_canvas.bind("<Configure>", self._resize_header_window)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(table_frame, highlightthickness=0, bg="#f5f7fb")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.horizontal_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self._sync_xview)
        self.horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

        self.rows_container = tk.Frame(self.canvas, bg="#f5f7fb")
        self.rows_window = self.canvas.create_window((0, 0), window=self.rows_container, anchor="nw")
        self.rows_container.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._resize_rows_window)
        self.canvas.configure(xscrollcommand=self._on_canvas_xscroll)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _reset_search(self) -> None:
        for variable in self.filter_vars.values():
            variable.set("")
        for variables in self.filter_check_vars.values():
            for variable in variables.values():
                variable.set(False)
        self.current_page = 0
        self.refresh()

    def _refresh_from_first_page(self) -> None:
        self.current_page = 0
        self.refresh()

    def _force_refresh(self) -> None:
        self._data_cache_key = None
        self._data_cache_rows = None
        self.refresh()

    @staticmethod
    def _column_width(column: str) -> int:
        if column == "row_number":
            return 60
        if column == "address":
            return 480
        if column in {"name", "category"}:
            return 320
        if column in {"count"}:
            return 140
        if column in {"inn", "contract"}:
            return 180
        return 220

    @staticmethod
    def _column_weight(column: str) -> int:
        if column == "address":
            return 4
        if column in {"name", "category"}:
            return 3
        if column in {"inn", "contract"}:
            return 2
        return 1

    def _get_filters(self) -> dict[str, str]:
        filters = {key: variable.get().strip() for key, variable in self.filter_vars.items()}
        for key, variables in self.filter_check_vars.items():
            selected = [value for value, variable in variables.items() if variable.get()]
            filters[key] = "|".join(selected)
        return filters

    def _set_result_count(self, count: int) -> None:
        self.result_count_label.configure(text=f"Найдено записей: {count}")

    @staticmethod
    def _wrap_value(value: object, width: int = 40) -> str:
        text = str(value) if value not in (None, "") else "—"
        return textwrap.fill(text, width=width, break_long_words=False, break_on_hyphens=False)

    @staticmethod
    def _format_inn_value(value: object) -> str:
        if value in (None, ""):
            return "—"
        return str(value).replace("|", "\n")

    @staticmethod
    def _row_tag(index: int) -> str:
        return "evenrow" if index % 2 == 0 else "oddrow"

    @staticmethod
    def _row_background(tag: str, selected: bool = False) -> str:
        if selected:
            return "#dfeeff"
        if tag == "evenrow":
            return "#f7f9fc"
        return "#ffffff"

    @staticmethod
    def _column_anchor(column: str) -> str:
        if column in {"row_number", "count"}:
            return "center"
        return "w"

    def _update_scrollregion(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_rows_window(self, event) -> None:
        self.canvas.itemconfigure(self.rows_window, width=max(event.width, self._content_width))

    def _update_header_scrollregion(self, _event=None) -> None:
        self.header_canvas.configure(scrollregion=self.header_canvas.bbox("all"))

    def _resize_header_window(self, event) -> None:
        self.header_canvas.itemconfigure(self.header_window, width=max(event.width, self._content_width))

    def _sync_xview(self, *args) -> None:
        self.canvas.xview(*args)
        self.header_canvas.xview(*args)

    def _on_canvas_xscroll(self, first, last) -> None:
        self.horizontal_scrollbar.set(first, last)
        try:
            current_first, _current_last = self.header_canvas.xview()
        except tk.TclError:
            return
        if abs(current_first - float(first)) > 0.0001:
            self.header_canvas.xview_moveto(first)

    def _on_mousewheel(self, event) -> None:
        if not self.winfo_ismapped():
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _clear_rows(self) -> None:
        self.selected_item_id = None
        self.row_frames.clear()
        for child in self.rows_container.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)

    def _insert_row(self, iid: int, values: tuple[object, ...], row_index: int) -> None:
        tag = self._row_tag(row_index)
        background = self._row_background(tag)
        row_frame = tk.Frame(
            self.rows_container,
            bg=background,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        row_frame.pack(fill="x", padx=(0, 2), pady=(0, 1))

        labels: list[tk.Label] = []
        for index, (column, value) in enumerate(zip(self.columns, values, strict=True)):
            row_frame.grid_columnconfigure(index, minsize=self._column_width(column), weight=self._column_weight(column))
            label = tk.Label(
                row_frame,
                text=str(value),
                bg=background,
                fg="#111827",
                justify="left",
                anchor=self._column_anchor(column),
                padx=10,
                pady=8,
                wraplength=max(self._column_width(column) - 24, 40),
                font=("Arial", 11),
            )
            label.grid(row=0, column=index, sticky="nsew")
            make_copyable(label)
            labels.append(label)

        self.row_frames[iid] = (row_frame, labels)
        self._bind_row_events(iid, row_frame, labels)

    def _bind_row_events(self, iid: int, row_frame: tk.Frame, labels: list[tk.Label]) -> None:
        widgets: list[tk.Widget] = [row_frame, *labels]
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, item_id=iid: self._select_row(item_id))
            widget.bind("<Double-Button-1>", lambda _event, item_id=iid: self._open_row(item_id))

    def _select_row(self, iid: int) -> None:
        if self.selected_item_id == iid:
            return
        previous = self.selected_item_id
        self.selected_item_id = iid
        if previous is not None:
            self._paint_row(previous, selected=False)
        self._paint_row(iid, selected=True)

    def _paint_row(self, iid: int, selected: bool) -> None:
        row_data = self.row_frames.get(iid)
        if row_data is None:
            return
        row_frame, labels = row_data
        tag = "evenrow" if list(self.row_frames).index(iid) % 2 == 0 else "oddrow"
        background = self._row_background(tag, selected=selected)
        row_frame.configure(bg=background)
        for label in labels:
            label.configure(bg=background)

    def _open_row(self, iid: int) -> None:
        self._select_row(iid)
        self.open_selected()

    def _set_rows_data(self, rows_data: list[tuple[int, tuple[object, ...]]]) -> None:
        self._rows_data = rows_data
        self._clear_rows()
        start = self.current_page * self.page_size
        for visual_index, (iid, values) in enumerate(self._rows_data, start=start + 1):
            self._insert_row(iid, values, visual_index)
        total_pages = max(1, (self._total_rows + self.page_size - 1) // self.page_size)
        self.page_label.configure(text=f"Страница {self.current_page + 1} из {total_pages}")
        self.prev_page_button.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_page_button.configure(
            state="normal" if (self.current_page + 1) * self.page_size < self._total_rows else "disabled"
        )
        self._loaded = True
        self._dirty = False

    def _prev_page(self) -> None:
        if self.current_page <= 0:
            return
        self.current_page -= 1
        self.refresh()

    def _next_page(self) -> None:
        if (self.current_page + 1) * self.page_size >= self._total_rows:
            return
        self.current_page += 1
        self.refresh()

    def _set_page_data(self, rows_data: list[tuple[int, tuple[object, ...]]], total_rows: int) -> None:
        self._total_rows = total_rows
        max_page = max(0, (total_rows - 1) // self.page_size)
        if self.current_page > max_page:
            self.current_page = max_page
        self._set_rows_data(rows_data)

    def ensure_fresh(self, force: bool = False) -> None:
        if force or self._dirty or not self._loaded:
            self.refresh()

    def mark_dirty(self) -> None:
        self._dirty = True
        self._data_cache_key = None
        self._data_cache_rows = None

    def _filters_cache_key(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._get_filters().items()))

    def refresh(self) -> None:
        raise NotImplementedError

    def open_selected(self) -> None:
        raise NotImplementedError


class RealEstateTab(BaseTreeTab):
    columns = ("row_number", "address", "count")
    headings = ("№", "Адрес", "Связанных объектов отходов")
    filter_specs = (("address", "Адрес", 56),)

    def __init__(self, master, app: DesktopApp) -> None:
        super().__init__(master, app, "Недвижимость")

    def refresh(self) -> None:
        cache_key = self._filters_cache_key()
        if self._data_cache_key != cache_key or self._data_cache_rows is None:
            with SessionLocal() as db:
                rows = RealEstateRepository.list_with_counts(db, self._get_filters())
            self._data_cache_key = cache_key
            self._data_cache_rows = rows
        else:
            rows = self._data_cache_rows

        total = len(rows)
        start = self.current_page * self.page_size
        page_rows = rows[start : start + self.page_size]
        rows_data = [
            (
                entity.id,
                (
                    self.current_page * self.page_size + index,
                    self._wrap_value(entity.address, width=56),
                    count,
                ),
            )
            for index, (entity, count) in enumerate(page_rows, start=1)
        ]
        self._set_page_data(rows_data, total)
        self._set_result_count(total)

    def open_selected(self) -> None:
        if self.selected_item_id is None:
            messagebox.showinfo("Недвижимость", "Выберите объект для открытия.", parent=self)
            return
        self.app.show_dialog(RealEstateEditDialog, int(self.selected_item_id))


class WasteObjectTab(BaseTreeTab):
    columns = ("row_number", "name", "category", "address", "inn", "contract", "link_strategy")
    headings = ("№", "Наименование", "Категория", "Адрес", "ИНН", "Договор", "Сопоставление")
    filter_specs = (
        ("name", "Наименование", 24),
        ("category", "Категория", 22),
        ("address", "Адрес", 34),
        ("inn", "ИНН", 18),
        ("contract", "Договор", 16),
    )
    filter_check_specs = (
        (
            "link_strategy",
            "Сопоставление",
            (
                ("address_plus", "адрес+"),
                ("address_name_inn_plus", "адрес+имя+инн+"),
                ("address_name_inn_minus", "адрес+имя+инн-"),
                ("address_name_minus_inn_plus", "адрес+имя-инн+"),
            ),
        ),
    )

    def __init__(self, master, app: DesktopApp) -> None:
        super().__init__(master, app, "Объекты отходов")

    @staticmethod
    def _column_width(column: str) -> int:
        widths = {
            "row_number": 56,
            "name": 260,
            "category": 250,
            "address": 390,
            "inn": 150,
            "contract": 130,
            "link_strategy": 220,
        }
        return widths.get(column, BaseTreeTab._column_width(column))

    def refresh(self) -> None:
        cache_key = self._filters_cache_key()
        if self._data_cache_key != cache_key or self._data_cache_rows is None:
            with SessionLocal() as db:
                ordered_rows = WasteObjectRepository.list(db, self._get_filters())
            self._data_cache_key = cache_key
            self._data_cache_rows = ordered_rows
        else:
            ordered_rows = self._data_cache_rows

        total = len(ordered_rows)
        start = self.current_page * self.page_size
        page_rows = ordered_rows[start : start + self.page_size]
        rows_data = [
            (
                entity.id,
                (
                    self.current_page * self.page_size + index,
                    self._wrap_value(entity.name or "—", width=28),
                    self._wrap_value(entity.category or "—", width=28),
                    self._wrap_value(entity.real_estate.address, width=44),
                    self._format_inn_value(entity.inn),
                    entity.contract_number or "—",
                    format_contract_link_display(entity),
                ),
            )
            for index, entity in enumerate(page_rows, start=1)
        ]
        self._set_page_data(rows_data, total)
        self._set_result_count(total)

    def open_selected(self) -> None:
        if self.selected_item_id is None:
            messagebox.showinfo("Объекты отходов", "Выберите объект для открытия.", parent=self)
            return
        self.app.show_dialog(WasteObjectEditDialog, int(self.selected_item_id))


class ContractRowsTab(BaseTreeTab):
    columns = (
        "row_number",
        "contract_number",
        "contract_date",
        "legal_entity_name",
        "waste_object_name",
        "inn",
        "address",
    )
    headings = (
        "№",
        "Договор",
        "Дата",
        "Потребитель",
        "Наименование ИОО",
        "ИНН",
        "Адрес",
    )
    filter_specs = (
        ("contract_number", "Договор", 18),
        ("waste_object_name", "Наименование ИОО", 26),
        ("inn", "ИНН", 18),
        ("address", "Адрес", 30),
    )

    def __init__(self, master, app: DesktopApp) -> None:
        super().__init__(master, app, "Договоры к разбору")

    @staticmethod
    def _column_width(column: str) -> int:
        widths = {
            "row_number": 56,
            "contract_number": 120,
            "contract_date": 110,
            "legal_entity_name": 250,
            "waste_object_name": 240,
            "inn": 150,
            "address": 360,
        }
        return widths.get(column, BaseTreeTab._column_width(column))

    def refresh(self) -> None:
        cache_key = self._filters_cache_key()
        if self._data_cache_key != cache_key or self._data_cache_rows is None:
            with SessionLocal() as db:
                rows = ContractRowRepository.list_unresolved(db, self._get_filters())
            self._data_cache_key = cache_key
            self._data_cache_rows = rows
        else:
            rows = self._data_cache_rows

        total = len(rows)
        start = self.current_page * self.page_size
        page_rows = rows[start : start + self.page_size]
        rows_data = [
            (
                entity.id,
                (
                    self.current_page * self.page_size + index,
                    entity.contract_number or "—",
                    entity.contract_date.strftime("%d.%m.%Y") if entity.contract_date else "—",
                    self._wrap_value(entity.legal_entity_name or "—", width=26),
                    self._wrap_value(entity.waste_object_name or "—", width=24),
                    self._format_inn_value(entity.inn),
                    self._wrap_value(entity.address or "—", width=40),
                ),
            )
            for index, entity in enumerate(page_rows, start=1)
        ]
        self._set_page_data(rows_data, total)
        self._set_result_count(total)

    def open_selected(self) -> None:
        if self.selected_item_id is None:
            messagebox.showinfo("Договоры к разбору", "Выберите строку договора для открытия.", parent=self)
            return
        self.app.show_dialog(ContractRowEditDialog, int(self.selected_item_id))


class LegalEntityTab(BaseTreeTab):
    columns = ("row_number", "inn", "name", "count")
    headings = ("№", "ИНН", "Наименование", "Связанных объектов отходов")
    filter_specs = (
        ("inn", "ИНН", 18),
        ("name", "Наименование", 34),
    )

    def __init__(self, master, app: DesktopApp) -> None:
        super().__init__(master, app, "Юрлица")

    def refresh(self) -> None:
        cache_key = self._filters_cache_key()
        if self._data_cache_key != cache_key or self._data_cache_rows is None:
            with SessionLocal() as db:
                rows = LegalEntityRepository.list_with_counts(db, self._get_filters())
            self._data_cache_key = cache_key
            self._data_cache_rows = rows
        else:
            rows = self._data_cache_rows

        total = len(rows)
        start = self.current_page * self.page_size
        page_rows = rows[start : start + self.page_size]
        rows_data = [
            (
                entity.id,
                (
                    self.current_page * self.page_size + index,
                    entity.inn,
                    self._wrap_value(entity.name or "—", width=34),
                    count,
                ),
            )
            for index, (entity, count) in enumerate(page_rows, start=1)
        ]
        self._set_page_data(rows_data, total)
        self._set_result_count(total)

    def open_selected(self) -> None:
        if self.selected_item_id is None:
            messagebox.showinfo("Юрлица", "Выберите юридическое лицо для открытия.", parent=self)
            return
        self.app.show_dialog(LegalEntityEditDialog, int(self.selected_item_id))
