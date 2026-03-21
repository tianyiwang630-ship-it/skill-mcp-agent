import sys
import types
import uuid
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")

    class DummyOpenAI:  # pragma: no cover - test import shim only
        def __init__(self, *args, **kwargs):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **_: None))

    openai_stub.OpenAI = DummyOpenAI
    sys.modules["openai"] = openai_stub


if "tiktoken" not in sys.modules:
    tiktoken_stub = types.ModuleType("tiktoken")

    class DummyEncoding:  # pragma: no cover - test import shim only
        def encode(self, text):
            return list(text.encode("utf-8"))

    tiktoken_stub.get_encoding = lambda *_args, **_kwargs: DummyEncoding()
    tiktoken_stub.encoding_for_model = lambda *_args, **_kwargs: DummyEncoding()
    sys.modules["tiktoken"] = tiktoken_stub


def make_test_dir(name: str) -> Path:
    base = PROJECT_ROOT.parent / "temp" / "test-fixtures"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{name}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_test_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
