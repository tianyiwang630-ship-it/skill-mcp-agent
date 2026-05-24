from datetime import datetime
from pathlib import Path
import sys
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.cli.main import append_session_index, build_log_path, create_cli_session


def test_create_cli_session_returns_session_storage_and_default_workspace():
    tmp_dir = make_test_dir("main-cli-session")
    try:
        project_root = tmp_dir / "agent-alpha"

        sessions_dir, logs_dir, workspace_root = create_cli_session(project_root)

        assert sessions_dir == (project_root / "session-log" / "sessions").resolve()
        assert logs_dir == (project_root / "session-log" / "logs").resolve()
        assert workspace_root == (project_root / "workspace").resolve()
        assert sessions_dir.exists()
        assert logs_dir.exists()
        assert workspace_root.exists()
    finally:
        cleanup_test_dir(tmp_dir)


def test_build_log_path_uses_logs_dir_and_session_id():
    started_at = datetime(2026, 3, 22, 15, 30, 0)
    log_path = build_log_path(Path("D:/demo/workspace/logs"), "abc123", started_at)
    assert str(log_path).endswith("2026-03-22_15-30-00_session_abc123.json")


def test_append_session_index_records_workspace_and_log_file():
    tmp_dir = make_test_dir("main-session-index")
    try:
        project_root = tmp_dir / "agent-alpha"
        sessions_dir, logs_dir, workspace_root = create_cli_session(project_root)
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "draft.txt").write_text("draft", encoding="utf-8")
        log_path = logs_dir / "2026-03-22_15-30-00_session_abc123.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("{}", encoding="utf-8")

        append_session_index(
            sessions_dir=sessions_dir,
            session_id="abc123",
            started_at=datetime(2026, 3, 22, 15, 30, 0),
            history=[{"role": "user", "content": "hello world"}],
            workspace=workspace_root,
            log_path=log_path,
        )

        index_text = (sessions_dir / "index.md").read_text(encoding="utf-8")
        assert "abc123" in index_text
        assert "workspace" in index_text
        assert "session-log/logs/2026-03-22_15-30-00_session_abc123.json" in index_text
        assert "hello world" in index_text
    finally:
        cleanup_test_dir(tmp_dir)


def test_save_session_log_writes_to_session_log_folder():
    tmp_dir = make_test_dir("main-save-session-log")
    try:
        from agent.cli.main import save_session_log

        project_root = tmp_dir / "agent-alpha"
        sessions_dir, logs_dir, workspace_root = create_cli_session(project_root)
        log_path = build_log_path(logs_dir, "abc123", datetime(2026, 3, 22, 15, 30, 0))
        agent = SimpleNamespace(
            history=[{"role": "user", "content": "hello world"}],
            get_session_log_data=lambda: {"history": [{"role": "user", "content": "hello world"}]},
        )

        save_session_log(
            agent=agent,
            session_id="abc123",
            started_at=datetime(2026, 3, 22, 15, 30, 0),
            sessions_dir=sessions_dir,
            workspace=workspace_root,
            log_path=log_path,
        )

        assert log_path.exists()
        assert (sessions_dir / "index.md").exists()
    finally:
        cleanup_test_dir(tmp_dir)
