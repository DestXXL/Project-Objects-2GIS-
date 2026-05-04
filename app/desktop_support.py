from __future__ import annotations

import os
from pathlib import Path
import sys


APP_FOLDER_NAME = "WasteRegistryApp"


def desktop_data_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_FOLDER_NAME
    if sys.platform.startswith("win"):
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return appdata / APP_FOLDER_NAME
    xdg_data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return xdg_data_home / APP_FOLDER_NAME


def configure_desktop_environment() -> Path:
    data_dir = desktop_data_dir()
    os.environ.setdefault("WASTE_REGISTRY_DATA_DIR", str(data_dir))
    return data_dir
