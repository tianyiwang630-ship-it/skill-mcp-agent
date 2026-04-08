import importlib
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_api_package_exposes_llm_modules():
    from agent.api.llm import LLMClient
    from agent.api.llm_profiles import LLMProfile, load_llm_profile

    assert LLMClient is not None
    assert LLMProfile is not None
    assert callable(load_llm_profile)


def test_cli_package_exposes_main_helpers():
    from agent.cli.main import append_session_index, build_log_path, create_cli_session

    assert callable(create_cli_session)
    assert callable(build_log_path)
    assert callable(append_session_index)


def test_cli_package_import_does_not_preload_main_module():
    sys.modules.pop("agent.cli.main", None)
    sys.modules.pop("agent.cli", None)

    importlib.import_module("agent.cli")

    assert "agent.cli.main" not in sys.modules


def test_legacy_core_shims_are_removed():
    legacy_files = [
        PROJECT_ROOT / "agent" / "core" / "llm.py",
        PROJECT_ROOT / "agent" / "core" / "llm_profiles.py",
        PROJECT_ROOT / "agent" / "core" / "main.py",
        PROJECT_ROOT / "agent" / "core" / "core_agent.py",
    ]

    assert legacy_files == [path for path in legacy_files if not path.exists()]


def test_runtime_layout_files_exist():
    expected_files = [
        PROJECT_ROOT / "agent" / "core" / "agent_runtime.py",
        PROJECT_ROOT / "agent" / "core" / "role_config.py",
        PROJECT_ROOT / "agent" / "core" / "runtime_types.py",
        PROJECT_ROOT / "agent" / "runtime" / "bus" / "events.py",
        PROJECT_ROOT / "agent" / "runtime" / "bus" / "queue.py",
        PROJECT_ROOT / "agent" / "runtime" / "cron" / "service.py",
        PROJECT_ROOT / "agent" / "runtime" / "cron" / "types.py",
    ]

    assert expected_files == [path for path in expected_files if path.exists()]
