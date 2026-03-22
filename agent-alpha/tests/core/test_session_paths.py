from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.session_paths import create_cli_session_paths, ensure_agent_workspace


def test_ensure_agent_workspace_creates_input_output_temp():
    tmp_dir = make_test_dir("session-paths")
    try:
        workspace_root = tmp_dir / "workspace"

        paths = ensure_agent_workspace(workspace_root=workspace_root)

        assert paths.workspace_root == workspace_root.resolve()
        assert paths.input_dir == (workspace_root / "input").resolve()
        assert paths.output_dir == (workspace_root / "output").resolve()
        assert paths.temp_dir == (workspace_root / "temp").resolve()
        assert paths.input_dir.exists()
        assert paths.output_dir.exists()
        assert paths.temp_dir.exists()
    finally:
        cleanup_test_dir(tmp_dir)


def test_create_cli_session_paths_creates_session_workspace_and_logs():
    tmp_dir = make_test_dir("cli-session-paths")
    try:
        workspace_root = tmp_dir / "workspace"

        paths = create_cli_session_paths(workspace_root=workspace_root, session_id="abc123")

        assert paths.session_root == (workspace_root / "sessions" / "abc123").resolve()
        assert paths.logs_dir == (workspace_root / "logs").resolve()
        assert paths.workspace_paths.input_dir == (workspace_root / "sessions" / "abc123" / "input").resolve()
        assert paths.workspace_paths.output_dir == (workspace_root / "sessions" / "abc123" / "output").resolve()
        assert paths.workspace_paths.temp_dir == (workspace_root / "sessions" / "abc123" / "temp").resolve()
        assert paths.logs_dir.exists()
    finally:
        cleanup_test_dir(tmp_dir)
