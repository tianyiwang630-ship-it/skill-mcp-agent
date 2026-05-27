import os
import sys
from pathlib import Path

from agent.core.agent_runtime import configure_python_environment


def test_configure_python_environment_exports_runtime_paths(monkeypatch):
    project_root = Path("D:/demo/agent-alpha")
    scripts_dir = str(Path(sys.executable).resolve().parent)
    monkeypatch.setenv("PATH", "C:/Other/Bin")
    monkeypatch.delenv("AGENT_ALPHA_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("AGENT_ALPHA_PYTHON", raising=False)
    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)
    monkeypatch.delenv("PIP_REQUIRE_VIRTUALENV", raising=False)

    configure_python_environment(project_root)

    assert os.environ["AGENT_ALPHA_PROJECT_ROOT"] == str(project_root.resolve())
    assert os.environ["AGENT_ALPHA_PYTHON"] == str(Path(sys.executable).resolve())
    assert os.environ["PYTHONNOUSERSITE"] == "1"
    assert os.environ["PIP_REQUIRE_VIRTUALENV"] == "true"
    assert os.environ["PATH"].split(os.pathsep)[0] == scripts_dir
