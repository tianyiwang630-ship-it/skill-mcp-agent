import json
from pathlib import Path

from agent.discovery.mcp_scanner import MCPScanner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYWRIGHT_DIR = PROJECT_ROOT / "mcp-servers" / "playwright"


def test_playwright_mcp_assets_are_removed():
    assert not PLAYWRIGHT_DIR.exists()


def test_playwright_mcp_is_not_registered_or_discovered():
    registry_path = PROJECT_ROOT / "mcp-servers" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    discovered = MCPScanner(str(PROJECT_ROOT / "mcp-servers")).scan()

    assert "playwright" not in registry
    assert "playwright" not in discovered
