from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.system_prompt_builder import build_system_prompt


def test_system_prompt_includes_runtime_paths_skills_mcp_and_prompt_docs():
    private_workspace = Path("D:/demo/workspaces/agent-a")
    additional_workspaces = [
        Path("D:/demo/workspaces/project-shared"),
        Path("D:/demo/workspaces/peer-agent"),
    ]
    logs_dir = Path("D:/demo/workspace/logs")
    skills_dir = Path("D:/demo/project/skills")
    mcp_servers_dir = Path("D:/demo/project/mcp-servers")
    mcp_registry_path = mcp_servers_dir / "registry.json"

    prompt = build_system_prompt(
        private_workspace=private_workspace,
        additional_workspaces=additional_workspaces,
        logs_dir=logs_dir,
        skills_dir=skills_dir,
        mcp_servers_dir=mcp_servers_dir,
        mcp_registry_path=mcp_registry_path,
        task_id="task-1",
        skill_summaries=[
            {
                "name": "pdf",
                "description": "Process PDF files",
                "path": str(skills_dir / "pdf" / "SKILL.md"),
            },
            {"name": "review", "description": "Review code changes"},
        ],
        prompt_documents=[
            {
                "name": "AGENTS.md",
                "path": str(private_workspace / "AGENTS.md"),
                "content": "Follow the session rules.",
            },
            {
                "name": "SOUL.md",
                "path": str(private_workspace / "SOUL.md"),
                "content": "You are a calm research agent.",
            },
        ],
    )

    assert "task-1" in prompt
    assert "## Private Workspace" in prompt
    assert "## Additional Workspaces" in prompt
    assert "## System Resource Paths" in prompt
    assert "## Runtime Records" in prompt
    assert str(private_workspace) in prompt
    assert str(additional_workspaces[0]) in prompt
    assert str(additional_workspaces[1]) in prompt
    assert str(logs_dir) in prompt
    assert str(skills_dir) in prompt
    assert str(mcp_servers_dir) in prompt
    assert str(mcp_registry_path) in prompt
    assert "AGENTS.md and SOUL.md are only loaded from the private workspace root" in prompt
    assert "If multiple workspaces are provided, their roles should be interpreted from AGENTS.md" in prompt
    assert "System resource paths are primarily for reading and reference" in prompt
    assert "Logs are runtime records" in prompt
    assert "Skills available:" in prompt
    assert "- pdf: Process PDF files" in prompt
    assert str(skills_dir / "pdf" / "SKILL.md") in prompt
    assert "- review: Review code changes" in prompt
    assert "load_skill" in prompt
    assert "AGENTS.md" in prompt
    assert "Follow the session rules." in prompt
    assert "SOUL.md" in prompt
    assert "You are a calm research agent." in prompt
