from pathlib import Path

from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.skill_installer import install_skill, list_skills, remove_skill


def _write_skill(path: Path, *, name: str, description: str, body: str = "Use carefully.") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"""---
name: {name}
description: {description}
---
{body}
""",
        encoding="utf-8",
    )


def test_install_skill_defaults_to_project_skills_dir():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "demo"
        project_root = tmp_dir / "project"
        _write_skill(source, name="demo", description="Demo skill")

        result = install_skill(source=str(source), project_root=project_root)

        assert result.name == "demo"
        assert result.scope == "project"
        assert (project_root / "skills" / "demo" / "SKILL.md").exists()
        assert (project_root / "skills" / ".install-lock.json").exists()
        assert list((project_root / "temp" / "skill-installer").glob("*")) == []
    finally:
        cleanup_test_dir(tmp_dir)


def test_install_skill_supports_workspace_scope():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "workspace-demo"
        project_root = tmp_dir / "project"
        workspace = tmp_dir / "workspace-a"
        _write_skill(source, name="workspace-demo", description="Workspace skill")

        result = install_skill(
            source=str(source),
            project_root=project_root,
            scope="workspace",
            workspace=workspace,
        )

        assert result.scope == "workspace"
        assert (workspace / "skills" / "workspace-demo" / "SKILL.md").exists()
        assert (workspace / "skills" / ".install-lock.json").exists()
    finally:
        cleanup_test_dir(tmp_dir)


def test_install_skill_rejects_missing_description():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "bad"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            """---
name: bad
---
Body.
""",
            encoding="utf-8",
        )

        try:
            install_skill(source=str(source), project_root=tmp_dir / "project")
        except ValueError as exc:
            assert "description" in str(exc)
        else:
            raise AssertionError("Expected missing description to be rejected.")
    finally:
        cleanup_test_dir(tmp_dir)


def test_list_skills_marks_project_skill_overridden_by_workspace():
    tmp_dir = make_test_dir("skill-installer")
    try:
        project_root = tmp_dir / "project"
        workspace = tmp_dir / "workspace"
        _write_skill(project_root / "skills" / "shared", name="shared", description="Project")
        _write_skill(workspace / "skills" / "shared", name="shared", description="Workspace")

        entries = list_skills(project_root=project_root, workspace=workspace, scope="all")

        assert [entry["scope"] for entry in entries] == ["workspace", "project"]
        assert entries[0]["status"] == "active"
        assert entries[1]["status"] == "overridden"
    finally:
        cleanup_test_dir(tmp_dir)


def test_remove_skill_removes_selected_scope():
    tmp_dir = make_test_dir("skill-installer")
    try:
        project_root = tmp_dir / "project"
        _write_skill(project_root / "skills" / "demo", name="demo", description="Demo")

        removed = remove_skill(project_root=project_root, name="demo", scope="project")

        assert removed == project_root / "skills" / "demo"
        assert not removed.exists()
    finally:
        cleanup_test_dir(tmp_dir)
