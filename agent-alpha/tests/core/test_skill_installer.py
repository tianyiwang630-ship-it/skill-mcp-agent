from pathlib import Path

from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.skill_installer import inspect_skill_source, install_skill, list_skills, remove_skill


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


def test_inspect_source_finds_root_skill_and_linked_install_doc():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "web-access"
        _write_skill(source, name="web-access", description="Browse the web")
        (source / "README.md").write_text(
            "[Install](docs/INSTALL.md)\n\n```bash\nnpm install\n```\n",
            encoding="utf-8",
        )
        docs = source / "docs"
        docs.mkdir()
        (docs / "INSTALL.md").write_text(
            "```bash\nuv tool install web-access-helper\n```\n",
            encoding="utf-8",
        )

        result = inspect_skill_source(source=str(source), project_root=tmp_dir / "project")

        assert result.kind == "single"
        assert [candidate.install_name for candidate in result.candidates] == ["web-access"]
        assert sorted(doc.relative_path for doc in result.docs) == ["README.md", "docs/INSTALL.md"]
        assert [command.command for command in result.dependency_commands] == [
            "npm install",
            "uv tool install web-access-helper",
        ]
    finally:
        cleanup_test_dir(tmp_dir)


def test_inspect_source_finds_single_nested_skill():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "Agent-Reach"
        _write_skill(source / "agent_reach" / "skill", name="agent-reach", description="Reach other agents")
        (source / "README.md").write_text(
            "Install with:\n\n```bash\nuv tool install agent-reach\n```\n",
            encoding="utf-8",
        )

        result = inspect_skill_source(source=str(source), project_root=tmp_dir / "project")

        assert result.kind == "single"
        assert result.candidates[0].relative_path == "agent_reach/skill/SKILL.md"
        assert result.candidates[0].install_name == "agent-reach"
        assert result.dependency_commands[0].kind == "uv-tool"
    finally:
        cleanup_test_dir(tmp_dir)


def test_install_all_skill_pack_uses_namespace_and_records_lock():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "superpowers"
        _write_skill(source / "skills" / "development" / "brainstorming", name="brainstorming", description="Think first")
        _write_skill(source / "skills" / "development" / "writing-plans", name="writing-plans", description="Plan work")
        project_root = tmp_dir / "project"

        result = install_skill(source=str(source), project_root=project_root, install_all=True, namespace="superpowers")

        assert result.name == "superpowers"
        assert sorted(path.name for path in result.install_dirs) == ["brainstorming", "writing-plans"]
        assert (project_root / "skills" / "superpowers" / "brainstorming" / "SKILL.md").exists()
        assert (project_root / "skills" / "superpowers" / "writing-plans" / "SKILL.md").exists()

        lock = (project_root / "skills" / ".install-lock.json").read_text(encoding="utf-8")
        assert '"namespace": "superpowers"' in lock
        assert '"skills": [' in lock
    finally:
        cleanup_test_dir(tmp_dir)


def test_dry_run_with_deps_does_not_install_files_but_returns_plan():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "agent-reach"
        _write_skill(source, name="agent-reach", description="Reach other agents")
        (source / "README.md").write_text("```bash\nuv tool install agent-reach\n```\n", encoding="utf-8")
        project_root = tmp_dir / "project"

        result = install_skill(source=str(source), project_root=project_root, dry_run=True, with_deps=True)

        assert result.name == "agent-reach"
        assert result.install_dirs == []
        assert result.dependency_commands[0].command == "uv tool install agent-reach"
        assert not (project_root / "skills" / "agent-reach").exists()
    finally:
        cleanup_test_dir(tmp_dir)


def test_inspect_normalizes_python_dependency_commands_to_agent_runtime_python():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "python-skill"
        _write_skill(source, name="python-skill", description="Needs Python packages")
        (source / "README.md").write_text(
            "```bash\npip install rich typer\nuv pip install pyyaml\n```\n",
            encoding="utf-8",
        )

        result = inspect_skill_source(source=str(source), project_root=tmp_dir / "project")

        assert [command.command for command in result.dependency_commands] == [
            "uv pip install --python <AGENT_ALPHA_PYTHON> rich typer",
            "uv pip install --python <AGENT_ALPHA_PYTHON> pyyaml",
        ]
        assert [command.kind for command in result.dependency_commands] == ["uv-pip", "uv-pip"]
    finally:
        cleanup_test_dir(tmp_dir)


def test_inspect_dependency_plan_rejects_chained_shell_commands():
    tmp_dir = make_test_dir("skill-installer")
    try:
        source = tmp_dir / "source" / "unsafe-skill"
        _write_skill(source, name="unsafe-skill", description="Has unsafe docs")
        (source / "README.md").write_text(
            "```bash\nnpm install left-pad && echo bad\nuv tool install safe-tool\n```\n",
            encoding="utf-8",
        )

        result = inspect_skill_source(source=str(source), project_root=tmp_dir / "project")

        assert [command.command for command in result.dependency_commands] == ["uv tool install safe-tool"]
    finally:
        cleanup_test_dir(tmp_dir)
