from pathlib import Path

from app.services.project_service import ProjectService


def test_project_service_creates_default_project_manifest(tmp_path: Path):
    manifest_path = tmp_path / "projects.json"
    projects_dir = tmp_path / "projects"

    service = ProjectService(manifest_path=manifest_path, projects_dir=projects_dir)
    projects = service.list_projects()
    current = service.get_current_project()

    assert manifest_path.exists()
    assert len(projects) == 1
    assert projects[0].id == "default"
    assert current.id == "default"


def test_project_service_creates_and_selects_new_project(tmp_path: Path):
    service = ProjectService(manifest_path=tmp_path / "projects.json", projects_dir=tmp_path / "projects")

    project = service.create_project(" Рубцовск 2026 ")
    current = service.get_current_project()

    assert project.name == "Рубцовск 2026"
    assert current.id == project.id
    assert project.database_path.parent == tmp_path / "projects"
    assert project.database_path.suffix == ".db"


def test_project_service_switches_current_project(tmp_path: Path):
    service = ProjectService(manifest_path=tmp_path / "projects.json", projects_dir=tmp_path / "projects")
    first = service.get_current_project()
    second = service.create_project("Второй проект")

    selected = service.set_current_project(first.id)

    assert second.id != first.id
    assert selected.id == first.id
    assert service.get_current_project().id == first.id


def test_project_service_rejects_duplicate_project_names(tmp_path: Path):
    service = ProjectService(manifest_path=tmp_path / "projects.json", projects_dir=tmp_path / "projects")
    service.create_project("Проект")

    try:
        service.create_project("  проект  ")
    except ValueError as exc:
        assert "уже существует" in str(exc)
    else:
        raise AssertionError("Expected duplicate project name to be rejected")
