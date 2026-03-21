from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tests.conftest import cleanup_test_dir, make_test_dir
from agent.core.prompt_docs_loader import load_session_prompt_documents


def test_load_session_prompt_documents_reads_agents_and_soul():
    tmp_dir = make_test_dir("prompt-docs")
    try:
        input_dir = tmp_dir / "sessions" / "abc123" / "input"
        input_dir.mkdir(parents=True)
        (input_dir / "AGENTS.md").write_text("Session rules", encoding="utf-8")
        (input_dir / "SOUL.md").write_text("Session persona", encoding="utf-8")
        (input_dir / "IGNORE.md").write_text("ignored", encoding="utf-8")

        docs = load_session_prompt_documents(input_dir)

        assert [doc["name"] for doc in docs] == ["AGENTS.md", "SOUL.md"]
        assert docs[0]["content"] == "Session rules"
        assert docs[1]["content"] == "Session persona"
        assert docs[0]["path"].endswith("AGENTS.md")
        assert docs[1]["path"].endswith("SOUL.md")
    finally:
        cleanup_test_dir(tmp_dir)
