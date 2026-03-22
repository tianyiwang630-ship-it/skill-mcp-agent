from datetime import datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.main import append_session_index, build_log_path, create_cli_session


def test_create_cli_session_returns_session_workspace_and_logs_dir():
    tmp_dir = make_test_dir("main-cli-session")
    try:
        workspace_root = tmp_dir / "workspace"

        session_workspace, logs_dir = create_cli_session(workspace_root, "abc123")

        assert session_workspace == (workspace_root / "sessions" / "abc123").resolve()
        assert (session_workspace / "input").exists()
        assert (session_workspace / "output").exists()
        assert (session_workspace / "temp").exists()
        assert logs_dir == (workspace_root / "logs").resolve()
    finally:
        cleanup_test_dir(tmp_dir)


def test_build_log_path_uses_logs_dir_and_session_id():
    started_at = datetime(2026, 3, 22, 15, 30, 0)
    log_path = build_log_path(Path("D:/demo/workspace/logs"), "abc123", started_at)
    assert str(log_path).endswith("2026-03-22_15-30-00_session_abc123.json")


def test_append_session_index_records_temp_dir_and_log_file():
    tmp_dir = make_test_dir("main-session-index")
    try:
        workspace_root = tmp_dir / "workspace"
        session_workspace, _logs_dir = create_cli_session(workspace_root, "abc123")
        temp_dir = session_workspace / "temp"
        (temp_dir / "draft.txt").write_text("draft", encoding="utf-8")
        log_path = workspace_root / "logs" / "2026-03-22_15-30-00_session_abc123.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("{}", encoding="utf-8")

        append_session_index(
            workspace_root=workspace_root,
            session_id="abc123",
            started_at=datetime(2026, 3, 22, 15, 30, 0),
            history=[{"role": "user", "content": "hello world"}],
            session_workspace=session_workspace,
            temp_dir=temp_dir,
            log_path=log_path,
        )

        index_text = (workspace_root / "sessions" / "index.md").read_text(encoding="utf-8")
        assert "abc123" in index_text
        assert "sessions/abc123/temp" in index_text
        assert "logs/2026-03-22_15-30-00_session_abc123.json" in index_text
        assert "hello world" in index_text
    finally:
        cleanup_test_dir(tmp_dir)
