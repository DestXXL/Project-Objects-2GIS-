from __future__ import annotations

import sys

from app.desktop_support import configure_desktop_environment


def main() -> None:
    configure_desktop_environment()

    try:
        from app.gui.main_window import run_desktop_app
    except ModuleNotFoundError as exc:
        if exc.name == "_tkinter":
            raise SystemExit(
                "Не удалось запустить desktop-приложение: в текущем Python отсутствует модуль Tkinter.\n\n"
                "Что сделать:\n"
                "1. Установить Python с поддержкой Tkinter.\n"
                "2. Пересоздать виртуальное окружение именно на этом Python.\n"
                "3. Снова установить зависимости и запустить: python -m app.desktop\n\n"
                "Проверка Tkinter:\n"
                "python -c \"import tkinter as tk; root = tk.Tk(); root.destroy(); print('Tk OK')\"\n\n"
                f"Текущий Python: {sys.executable}"
            ) from exc
        raise

    run_desktop_app()


if __name__ == "__main__":
    main()
