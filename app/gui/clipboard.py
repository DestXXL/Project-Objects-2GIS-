from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


def install_clipboard_support(root: tk.Misc) -> None:
    for class_name in ("Entry", "TEntry", "Text"):
        root.bind_class(class_name, "<Control-a>", _select_all, add="+")
        root.bind_class(class_name, "<Control-A>", _select_all, add="+")
        root.bind_class(class_name, "<Command-a>", _select_all, add="+")
        root.bind_class(class_name, "<Command-A>", _select_all, add="+")
        root.bind_class(class_name, "<Button-3>", _show_edit_menu, add="+")
        root.bind_class(class_name, "<Button-2>", _show_edit_menu, add="+")


def attach_edit_menu(widget: tk.Widget) -> None:
    widget.bind("<Button-3>", _show_edit_menu, add="+")
    widget.bind("<Button-2>", _show_edit_menu, add="+")


def make_copyable(widget: tk.Widget, text_getter: Optional[Callable[[], str]] = None) -> None:
    widget.bind("<Double-Button-1>", lambda event: _copy_static_widget_text(event, text_getter), add="+")
    widget.bind("<Control-c>", lambda event: _copy_static_widget_text(event, text_getter), add="+")
    widget.bind("<Control-C>", lambda event: _copy_static_widget_text(event, text_getter), add="+")
    widget.bind("<Command-c>", lambda event: _copy_static_widget_text(event, text_getter), add="+")
    widget.bind("<Command-C>", lambda event: _copy_static_widget_text(event, text_getter), add="+")
    widget.bind("<Button-3>", lambda event: _show_copy_menu(event, text_getter), add="+")
    widget.bind("<Button-2>", lambda event: _show_copy_menu(event, text_getter), add="+")
    for option, value in (("takefocus", 0), ("highlightthickness", 0), ("bd", 0), ("relief", "flat")):
        try:
            widget.configure(**{option: value})
        except tk.TclError:
            continue


def _copy_static_widget_text(event, text_getter: Optional[Callable[[], str]] = None):
    widget = event.widget
    text = text_getter() if text_getter is not None else str(widget.cget("text"))
    text = text.strip()
    if not text or text == "—":
        return "break"
    widget.clipboard_clear()
    widget.clipboard_append(text)
    return "break"


def _select_all(event):
    widget = event.widget
    if isinstance(widget, tk.Text):
        widget.tag_add("sel", "1.0", "end-1c")
        return "break"
    if isinstance(widget, (tk.Entry, ttk.Entry)):
        widget.select_range(0, "end")
        widget.icursor("end")
        return "break"
    return None


def _show_edit_menu(event):
    widget = event.widget
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: _select_all(_SyntheticEvent(widget)))
    menu.tk_popup(event.x_root, event.y_root)
    return "break"


def _show_copy_menu(event, text_getter: Optional[Callable[[], str]] = None):
    widget = event.widget
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Копировать текст", command=lambda: _copy_text_from_widget(widget, text_getter))
    menu.tk_popup(event.x_root, event.y_root)
    return "break"


def _copy_text_from_widget(widget: tk.Widget, text_getter: Optional[Callable[[], str]] = None) -> None:
    text = text_getter() if text_getter is not None else str(widget.cget("text"))
    text = text.strip()
    if not text or text == "—":
        return
    widget.clipboard_clear()
    widget.clipboard_append(text)


class _SyntheticEvent:
    def __init__(self, widget: tk.Widget) -> None:
        self.widget = widget
