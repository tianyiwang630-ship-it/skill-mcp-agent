from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.prompt_docs_loader import load_workspace_prompt_documents


def test_load_workspace_prompt_documents_reads_first_workspace_root_docs():
    tmp_dir = make_test_dir("prompt-docs")
    try:
        first_workspace = tmp_dir / "workspace-a"
        second_workspace = tmp_dir / "workspace-b"
        nested = first_workspace / "nested"
        nested.mkdir(parents=True)
        second_workspace.mkdir(parents=True)
        (first_workspace / "AGENTS.md").write_text("Private rules", encoding="utf-8")
        (first_workspace / "SOUL.md").write_text("Private persona", encoding="utf-8")
        (nested / "AGENTS.md").write_text("nested should be ignored", encoding="utf-8")
        (second_workspace / "AGENTS.md").write_text("other workspace ignored", encoding="utf-8")

        docs = load_workspace_prompt_documents([first_workspace, second_workspace])

        assert [doc["name"] for doc in docs] == ["AGENTS.md", "SOUL.md"]
        assert docs[0]["content"] == "Private rules"
        assert docs[1]["content"] == "Private persona"
        assert docs[0]["path"].endswith("AGENTS.md")
        assert docs[1]["path"].endswith("SOUL.md")
    finally:
        cleanup_test_dir(tmp_dir)
