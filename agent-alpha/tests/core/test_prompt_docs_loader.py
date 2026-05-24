from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.prompt_docs_loader import load_workspace_prompt_documents


def test_load_workspace_prompt_documents_reads_workspace_root_docs_only():
    tmp_dir = make_test_dir("prompt-docs")
    try:
        workspace_root = tmp_dir / "workspace"
        nested = workspace_root / "nested"
        nested.mkdir(parents=True)
        (workspace_root / "AGENTS.md").write_text("Private rules", encoding="utf-8")
        (workspace_root / "SOUL.md").write_text("Private persona", encoding="utf-8")
        (nested / "AGENTS.md").write_text("nested should be ignored", encoding="utf-8")

        docs = load_workspace_prompt_documents(workspace_root)

        assert [doc["name"] for doc in docs] == ["AGENTS.md", "SOUL.md"]
        assert docs[0]["content"] == "Private rules"
        assert docs[1]["content"] == "Private persona"
        assert docs[0]["path"].endswith("AGENTS.md")
        assert docs[1]["path"].endswith("SOUL.md")
    finally:
        cleanup_test_dir(tmp_dir)
