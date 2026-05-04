from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from pathlib import Path
from uuid import uuid4

from app.config import DATABASE_PATH, PROJECTS_DIR, PROJECTS_MANIFEST_PATH


@dataclass(frozen=True)
class ProjectInfo:
    id: str
    name: str
    database_path: Path
    created_at: str


class ProjectService:
    def __init__(
        self,
        manifest_path: Path = PROJECTS_MANIFEST_PATH,
        projects_dir: Path = PROJECTS_DIR,
    ) -> None:
        self.manifest_path = manifest_path
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_manifest()

    def list_projects(self) -> list[ProjectInfo]:
        manifest = self._read_manifest()
        return [self._project_from_record(record) for record in manifest["projects"]]

    def get_current_project(self) -> ProjectInfo:
        manifest = self._read_manifest()
        current_id = manifest.get("current_project_id")
        for record in manifest["projects"]:
            if record["id"] == current_id:
                return self._project_from_record(record)
        first = manifest["projects"][0]
        manifest["current_project_id"] = first["id"]
        self._write_manifest(manifest)
        return self._project_from_record(first)

    def set_current_project(self, project_id: str) -> ProjectInfo:
        manifest = self._read_manifest()
        for record in manifest["projects"]:
            if record["id"] == project_id:
                manifest["current_project_id"] = project_id
                self._write_manifest(manifest)
                return self._project_from_record(record)
        raise ValueError("Проект не найден.")

    def create_project(self, name: str) -> ProjectInfo:
        normalized_name = self._normalize_project_name(name)
        if not normalized_name:
            raise ValueError("Укажите название проекта.")

        manifest = self._read_manifest()
        existing_names = {record["name"].strip().lower() for record in manifest["projects"]}
        if normalized_name.lower() in existing_names:
            raise ValueError("Проект с таким названием уже существует.")

        project_id = uuid4().hex
        database_path = self.projects_dir / f"{self._slugify(normalized_name)}-{project_id[:8]}.db"
        record = {
            "id": project_id,
            "name": normalized_name,
            "database_path": str(database_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        manifest["projects"].append(record)
        manifest["current_project_id"] = project_id
        self._write_manifest(manifest)
        return self._project_from_record(record)

    def _ensure_manifest(self) -> None:
        if self.manifest_path.exists():
            return

        default_record = {
            "id": "default",
            "name": "Основной проект",
            "database_path": str(DATABASE_PATH),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write_manifest(
            {
                "current_project_id": "default",
                "projects": [default_record],
            }
        )

    def _read_manifest(self) -> dict:
        self._ensure_manifest()
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.manifest_path.unlink(missing_ok=True)
            self._ensure_manifest()
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

        projects = manifest.get("projects") or []
        if not projects:
            self.manifest_path.unlink(missing_ok=True)
            self._ensure_manifest()
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return manifest

    def _write_manifest(self, manifest: dict) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _project_from_record(record: dict) -> ProjectInfo:
        return ProjectInfo(
            id=str(record["id"]),
            name=str(record["name"]),
            database_path=Path(record["database_path"]),
            created_at=str(record.get("created_at") or ""),
        )

    @staticmethod
    def _normalize_project_name(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip())

    @staticmethod
    def _slugify(value: str) -> str:
        text = value.lower().replace("ё", "е")
        text = re.sub(r"[^a-z0-9а-я]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "project"
