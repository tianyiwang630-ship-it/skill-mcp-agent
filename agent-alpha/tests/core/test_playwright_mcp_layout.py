import json
from pathlib import Path

from agent.discovery.mcp_scanner import MCPScanner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYWRIGHT_DIR = PROJECT_ROOT / "mcp-servers" / "playwright"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_playwright_wrapper_files_exist():
    expected_paths = [
        PLAYWRIGHT_DIR / "package.json",
        PLAYWRIGHT_DIR / "server.js",
        PLAYWRIGHT_DIR / "mcp.config.json",
        PLAYWRIGHT_DIR / "playwright.headed.config.json",
        PLAYWRIGHT_DIR / "playwright.headless.config.json",
        PLAYWRIGHT_DIR / "state" / "profiles",
        PLAYWRIGHT_DIR / "state" / "storage",
    ]

    for path in expected_paths:
        assert path.exists(), f"Missing expected Playwright MCP asset: {path}"


def test_playwright_mcp_entry_uses_local_server_wrapper():
    config = _read_json(PLAYWRIGHT_DIR / "mcp.config.json")

    assert config["enabled"] is True
    assert config["type"] == "stdio"
    assert config["command"] == "node"
    assert config["args"] == ["server.js", "--config", "playwright.headed.config.json"]


def test_headed_config_uses_persistent_profile_and_syncs_before_close():
    config = _read_json(PLAYWRIGHT_DIR / "playwright.headed.config.json")

    assert config["mode"] == "headed"
    assert config["browser"]["isolated"] is False
    assert config["browser"]["launchOptions"]["headless"] is False
    assert config["browser"]["userDataDir"] == "state/profiles/default"
    assert config["sync"]["enabled"] is True
    assert config["sync"]["trigger"] == "before_close"
    assert config["sync"]["storageStatePath"] == "state/storage/shared.json"


def test_headless_config_uses_shared_storage_state():
    config = _read_json(PLAYWRIGHT_DIR / "playwright.headless.config.json")

    assert config["mode"] == "headless"
    assert config["browser"]["isolated"] is True
    assert config["browser"]["launchOptions"]["headless"] is True
    assert config["browser"]["contextOptions"]["storageState"] == "state/storage/shared.json"


def test_mcp_scanner_detects_local_playwright_wrapper():
    scanner = MCPScanner(str(PROJECT_ROOT / "mcp-servers"))

    discovered = scanner.scan()
    playwright = discovered["playwright"]

    assert playwright["type"] == "stdio"
    assert playwright["command"] == "node"
    assert playwright["args"] == ["server.js", "--config", "playwright.headed.config.json"]
    assert Path(playwright["cwd"]).resolve() == PLAYWRIGHT_DIR.resolve()
