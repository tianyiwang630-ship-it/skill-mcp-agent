from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.session_paths import create_cli_session_paths


def test_create_cli_session_paths_creates_session_workspace_and_logs():
    tmp_dir = make_test_dir("cli-session-paths")
    try:
        workspace_root = tmp_dir / "workspace"

        session_root, logs_dir = create_cli_session_paths(workspace_root=workspace_root, session_id="abc123")

        assert session_root == (workspace_root / "sessions" / "abc123").resolve()
        assert logs_dir == (workspace_root / "logs").resolve()
        assert session_root.exists()
        assert logs_dir.exists()
    finally:
        cleanup_test_dir(tmp_dir)
