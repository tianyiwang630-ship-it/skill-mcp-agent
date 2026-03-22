from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.system_prompt_builder import build_system_prompt


def test_system_prompt_includes_runtime_paths_skills_mcp_and_prompt_docs():
    workspace_root = Path("D:/demo/workspace/session-abc123")
    input_dir = workspace_root / "input"
    output_dir = workspace_root / "output"
    temp_dir = workspace_root / "temp"
    logs_dir = Path("D:/demo/workspace/logs")
    skills_dir = Path("D:/demo/project/skills")
    mcp_servers_dir = Path("D:/demo/project/mcp-servers")
    mcp_registry_path = mcp_servers_dir / "registry.json"

    prompt = build_system_prompt(
        workspace_root=workspace_root,
        input_dir=input_dir,
        output_dir=output_dir,
        temp_dir=temp_dir,
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
                "path": str(input_dir / "AGENTS.md"),
                "content": "Follow the session rules.",
            },
            {
                "name": "SOUL.md",
                "path": str(input_dir / "SOUL.md"),
                "content": "You are a calm research agent.",
            },
        ],
    )

    assert "task-1" in prompt
    assert "## Working Directories" in prompt
    assert "## System Resource Paths" in prompt
    assert "## Runtime Records" in prompt
    assert str(workspace_root) in prompt
    assert str(logs_dir) in prompt
    assert str(skills_dir) in prompt
    assert str(mcp_servers_dir) in prompt
    assert str(mcp_registry_path) in prompt
    assert "Write final deliverables to the output directory" in prompt
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
