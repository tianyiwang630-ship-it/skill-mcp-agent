from pathlib import Path

from tests.conftest import cleanup_test_dir, make_test_dir
from agent.cli import main as cli_main


def _write_skill(path: Path, *, name: str, description: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"""---
name: {name}
description: {description}
---
Use carefully.
""",
        encoding="utf-8",
    )


def test_skill_inspect_cli_lists_candidates(monkeypatch, capsys):
    tmp_dir = make_test_dir("skill-cli")
    try:
        source = tmp_dir / "source" / "agent-reach"
        project_root = tmp_dir / "project"
        _write_skill(source / "agent_reach" / "skill", name="agent-reach", description="Reach other agents")
        monkeypatch.setattr(cli_main, "PROJECT_ROOT", project_root)

        exit_code = cli_main.run_skill_cli(["inspect", str(source)])

        output = capsys.readouterr().out
        assert exit_code == 0
        assert "Kind: single" in output
        assert "agent-reach: Reach other agents" in output
        assert "agent_reach/skill/SKILL.md" in output
    finally:
        cleanup_test_dir(tmp_dir)


def test_skill_install_cli_supports_pack_dry_run(monkeypatch, capsys):
    tmp_dir = make_test_dir("skill-cli")
    try:
        source = tmp_dir / "source" / "superpowers"
        project_root = tmp_dir / "project"
        _write_skill(source / "skills" / "development" / "brainstorming", name="brainstorming", description="Think first")
        _write_skill(source / "skills" / "development" / "writing-plans", name="writing-plans", description="Plan work")
        monkeypatch.setattr(cli_main, "PROJECT_ROOT", project_root)

        exit_code = cli_main.run_skill_cli(["install", str(source), "--all", "--namespace", "superpowers", "--dry-run"])

        output = capsys.readouterr().out
        assert exit_code == 0
        assert "Dry run skill install: superpowers" in output
        assert "superpowers:brainstorming" in output
        assert "superpowers:writing-plans" in output
        assert not (project_root / "skills" / "superpowers").exists()
    finally:
        cleanup_test_dir(tmp_dir)
