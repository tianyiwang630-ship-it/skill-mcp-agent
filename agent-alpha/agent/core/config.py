"""
Configuration constants for Agent core components
Single source of truth for all system-wide settings
"""

# ========== Context Management ==========
MAX_CONTEXT_TOKENS = 200000  # Total context limit (200K)
KEEP_RECENT_TURNS = 10  # Turns to preserve during compression
COMPRESSION_THRESHOLD = 0.5  # Compress when history reaches 50% of available space
COMPRESSION_INPUT_RATIO = 0.9  # Summary LLM can receive up to 90% of max tokens

# ========== Tool Execution ==========
MAX_TOOL_RESULT_CHARS = 90000  # Truncate individual tool results to 30K chars
BASH_TOOL_TIMEOUT = 300  # Bash tool execution timeout (seconds)

# ========== LLM Responses ==========
LLM_MAX_TOKENS = 20000  # Default max tokens for LLM generation
LLM_SUMMARY_MAX_TOKENS = 4000  # Max tokens for compression summary

# ========== Encoding ==========
TIKTOKEN_ENCODING = "cl100k_base"  # Encoding for token counting

# ========== MCP Tool Search ==========
DEFAULT_MCP_CATEGORY = "searchable"  # Default category for MCP servers not in registry.json

# ========== LLM Configuration ==========
import os

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")