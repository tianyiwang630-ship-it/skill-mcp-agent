import json
from pathlib import Path
from unittest.mock import patch

from agent.core.runtime_env import load_runtime_env, redact_secrets, subprocess_env
from agent.tools.bash_tool import BashTool


def test_runtime_env_loads_local_profile(tmp_path):
    profile = tmp_path / "config" / "runtime_env.local.json"
    profile.parent.mkdir()
    profile.write_text(json.dumps({"env": {"TWITTER_AUTH_TOKEN": "secret-token"}}), encoding="utf-8")

    assert load_runtime_env(tmp_path) == {"TWITTER_AUTH_TOKEN": "secret-token"}


def test_runtime_env_injects_and_redacts_values(tmp_path):
    profile = tmp_path / "config" / "runtime_env.local.json"
    profile.parent.mkdir()
    profile.write_text(json.dumps({"env": {"TWITTER_AUTH_TOKEN": "secret-token"}}), encoding="utf-8")

    env = subprocess_env(tmp_path, {"PATH": "base"})

    assert env["TWITTER_AUTH_TOKEN"] == "secret-token"
    assert redact_secrets("value=secret-token", tmp_path) == "value=[REDACTED]"


def test_bash_tool_injects_runtime_env_and_redacts_output(tmp_path):
    profile = tmp_path / "config" / "runtime_env.local.json"
    profile.parent.mkdir()
    profile.write_text(json.dumps({"env": {"TWITTER_AUTH_TOKEN": "secret-token"}}), encoding="utf-8")

    tool = BashTool.__new__(BashTool)
    tool.timeout = 30
    tool.shell = "cmd"
    tool.project_root = tmp_path
    completed = type(
        "Completed",
        (),
        {"returncode": 0, "stdout": "secret-token\n", "stderr": "", "args": []},
    )()

    with patch("subprocess.run", return_value=completed) as run:
        result = tool.execute(command="echo secret-token")

    assert run.call_args.kwargs["env"]["TWITTER_AUTH_TOKEN"] == "secret-token"
    assert result["stdout"] == "[REDACTED]\n"
    assert result["command"] == "echo [REDACTED]"
