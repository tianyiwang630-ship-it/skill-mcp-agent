from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.session_paths import create_cli_session_paths, get_default_workspace_root


def test_create_cli_session_paths_creates_session_log_directories():
    tmp_dir = make_test_dir("cli-session-paths")
    try:
        project_root = tmp_dir / "agent-alpha"

        sessions_dir, logs_dir = create_cli_session_paths(project_root=project_root)

        assert sessions_dir == (project_root / "session-log" / "sessions").resolve()
        assert logs_dir == (project_root / "session-log" / "logs").resolve()
        assert sessions_dir.exists()
        assert logs_dir.exists()
    finally:
        cleanup_test_dir(tmp_dir)


def test_get_default_workspace_root_points_to_workspace_directory():
    project_root = Path("D:/demo/agent-alpha")

    workspace_root = get_default_workspace_root(project_root)

    assert workspace_root == (project_root / "workspace").resolve()
