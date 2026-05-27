from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Iterable

from agent.core.sandbox_types import AccessAction, BashCategory


READ_ONLY_SINGLE_COMMANDS = {"pwd"}
READ_ONLY_PATH_COMMANDS = {"ls", "dir", "cat", "type", "rg", "grep", "find"}
READ_ONLY_LOOKUP_COMMANDS = {"which", "where", "get-command", "test-path"}
VERSION_COMMANDS = {
    "python",
    "python3",
    "py",
    "pip",
    "pip3",
    "pipx",
    "uv",
    "node",
    "npm",
    "pnpm",
    "yarn",
    "git",
    "gh",
}
READ_ONLY_GIT_SUBCOMMANDS = {"status", "diff", "log", "show", "branch", "rev-parse", "ls-files"}
SCRIPT_RUNNERS = {"python", "python3", "py", "node"}
PACKAGE_INSTALL_PATTERNS = {
    ("pip", "install"),
    ("pip", "uninstall"),
    ("pipx", "install"),
    ("pipx", "uninstall"),
    ("npm", "install"),
    ("npm", "uninstall"),
    ("pnpm", "install"),
    ("pnpm", "add"),
    ("pnpm", "uninstall"),
    ("pnpm", "remove"),
    ("yarn", "install"),
    ("yarn", "add"),
    ("yarn", "uninstall"),
    ("yarn", "remove"),
    ("uv", "pip"),
    ("uv", "tool"),
}
PROJECT_COMMAND_PATTERNS = {
    ("pytest",),
    ("python", "-m"),
    ("python3", "-m"),
    ("py", "-m"),
    ("npm", "run"),
    ("pnpm", "run"),
    ("yarn", "run"),
}
DANGEROUS_COMMANDS = {
    "sudo",
    "su",
    "runas",
    "format",
    "mkfs",
    "diskpart",
    "shutdown",
    "reboot",
    "restart-computer",
    "stop-computer",
    "takeown",
    "icacls",
    "chmod",
    "chown",
    "set-executionpolicy",
    "invoke-expression",
    "iex",
    "start-process",
}
DANGEROUS_POWERSHELL_MUTATIONS = {
    "remove-item",
    "del",
    "erase",
    "rd",
    "rmdir",
}
DANGEROUS_POWERSHELL_ADMIN = {
    "set-itemproperty",
    "new-itemproperty",
    "remove-itemproperty",
    "set-acl",
    "disable-windowsoptionalfeature",
    "enable-windowsoptionalfeature",
    "bcdedit",
    "reg",
    "sc",
    "netsh",
}
MUTATION_COMMANDS = {"mkdir", "cp", "mv", "rm", "del", "rmdir", "touch", "tee", "sed", "echo", "git"}
CONTROL_OPERATORS = ("&&", "||", ";", "$(", "`")
CHAIN_OPERATORS = {"&&", "||", ";"}


def classify_bash_command(command: str) -> BashCategory:
    stripped = command.strip()
    if not stripped:
        return "unknown"

    tokens = _split_command(stripped)
    if not tokens:
        return "unknown"

    if _is_dangerous_command(stripped, tokens):
        return "dangerous"

    if _is_package_install(tokens):
        return "package_install"

    if _is_project_command(tokens):
        return "project_command"

    if _is_script_run(tokens):
        return "script_run"

    if _is_read_only_command(tokens):
        return "read_only"

    if _is_path_mutation_command(stripped, tokens):
        return "path_mutation"

    return "unknown"


def extract_script_path(command: str) -> Path | None:
    tokens = _split_command(command)
    if not _is_script_run(tokens):
        return None

    raw_path = _strip_quotes(tokens[1])
    if not raw_path:
        return None
    return _resolve_path(raw_path)


def extract_bash_paths(command: str, category: BashCategory) -> tuple[AccessAction, list[Path]] | None:
    if category == "read_only":
        return _extract_read_only_paths(command)

    if category == "path_mutation":
        return _extract_mutation_paths(command)

    return None


def explain_parseable_mutation_forms() -> str:
    return (
        "Use a simple single command with explicit paths. Supported writable forms include: "
        "mkdir path, cp src dst, mv src dst, rm file, del file, rmdir dir, touch file, "
        "echo ... > file, echo ... >> file, echo ... | tee file, echo ... | tee -a file, sed -i ... file, "
        "git checkout -- file, git restore file."
    )


def split_bash_segments(command: str) -> list[str] | None:
    """Split simple chained commands at &&, ||, and ; operators."""
    if "$(" in command or "`" in command:
        return None

    tokens = _split_command(command)
    if not tokens:
        return []

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in CHAIN_OPERATORS:
            if not segments[-1]:
                return None
            segments.append([])
            continue
        segments[-1].append(token)

    if any(not segment for segment in segments):
        return None
    return [" ".join(segment) for segment in segments]


def _extract_read_only_paths(command: str) -> tuple[AccessAction, list[Path]] | None:
    tokens = _split_command(command)
    if not tokens:
        return None

    first = _command_name(tokens[0])

    if first == "pwd":
        return "read", []

    if first == "echo" and not any(token in tokens for token in {">", ">>", "|"}) and not any(">" in token or "|" in token for token in tokens):
        return "read", []

    if first in VERSION_COMMANDS and any(token.lower() in {"--version", "-version", "-v"} for token in tokens[1:]):
        return "read", []

    if first in READ_ONLY_LOOKUP_COMMANDS:
        return "read", []

    if first == "git":
        return "read", []

    if first in {"ls", "dir"}:
        paths = [_resolve_path(_strip_quotes(token)) for token in tokens[1:] if not token.startswith("-")]
        paths = [path for path in paths if path is not None]
        return "read", paths

    if first in {"cat", "type"}:
        paths = [_resolve_path(_strip_quotes(token)) for token in tokens[1:] if not token.startswith("-")]
        if not paths:
            return None
        return "read", paths

    if first in {"rg", "grep"}:
        path = _extract_last_non_flag_path(tokens[1:])
        return ("read", [path]) if path else ("read", [])

    if first == "find":
        path = _extract_first_non_flag_path(tokens[1:])
        return ("read", [path]) if path else ("read", [])

    return None


def _extract_mutation_paths(command: str) -> tuple[AccessAction, list[Path]] | None:
    stripped = command.strip()

    tee_match = re.match(
        r"^\s*echo\b.*\|\s*tee(?:\s+(-a))?\s+(?P<path>\"[^\"]+\"|'[^']+'|\S+)\s*$",
        stripped,
        flags=re.IGNORECASE,
    )
    if tee_match:
        path = _resolve_path(_strip_quotes(tee_match.group("path")))
        return ("write", [path]) if path else None

    redirect_match = re.match(
        r"^\s*echo\b.*?(>>?)\s*(?P<path>\"[^\"]+\"|'[^']+'|\S+)\s*$",
        stripped,
        flags=re.IGNORECASE,
    )
    if redirect_match:
        path = _resolve_path(_strip_quotes(redirect_match.group("path")))
        return ("write", [path]) if path else None

    tokens = _split_command(stripped)
    if not tokens:
        return None

    command_name = tokens[0].lower()
    args = [token for token in tokens[1:] if token]

    if command_name == "mkdir":
        paths = _non_flag_paths(args)
        return ("write", paths) if len(paths) == 1 else None

    if command_name in {"cp", "mv"}:
        paths = _non_flag_paths(args)
        return ("write", paths) if len(paths) == 2 else None

    if command_name in {"rm", "del", "rmdir"}:
        paths = _non_flag_paths(args)
        return ("delete", paths) if len(paths) == 1 else None

    if command_name == "touch":
        paths = _non_flag_paths(args)
        return ("write", paths) if len(paths) == 1 else None

    if command_name == "sed":
        if "-i" not in [arg.lower() for arg in args]:
            return None
        paths = _non_flag_paths(args)
        return ("write", [paths[-1]]) if paths else None

    if command_name == "git":
        return _extract_git_mutation(args)

    return None


def _is_dangerous_command(command: str, tokens: list[str]) -> bool:
    first = _command_name(tokens[0])
    if first in DANGEROUS_COMMANDS:
        if first == "chmod":
            lowered = command.lower()
            return " 777" in lowered or " a+w" in lowered or " -r 777" in lowered
        return True
    if first in DANGEROUS_POWERSHELL_ADMIN:
        return True
    if first in DANGEROUS_POWERSHELL_MUTATIONS:
        lowered_tokens = {token.lower() for token in tokens[1:]}
        lowered_command = command.lower()
        if "-recurse" in lowered_tokens and "-force" in lowered_tokens:
            return True
        if any(target in lowered_command for target in [" c:\\", " c:/", " $env:userprofile", " $home", " ~"]):
            return True

    normalized = " ".join(token.lower() for token in tokens)
    return "rm -rf /" in normalized or "rm -fr /" in normalized or normalized.startswith("git clean -fd")


def _is_package_install(tokens: list[str]) -> bool:
    normalized = _normalized_tokens(tokens)
    lowered = tuple(normalized[:2])
    if lowered in PACKAGE_INSTALL_PATTERNS:
        return True
    if len(normalized) >= 4 and normalized[0] in {"python", "python3", "py"} and normalized[1:4] == ["-m", "pip", "install"]:
        return True
    if len(normalized) >= 3 and normalized[0] in {"python", "python3", "py"} and normalized[1:3] == ["-m", "venv"]:
        return True
    return len(normalized) >= 2 and normalized[1] == "install"


def _is_project_command(tokens: list[str]) -> bool:
    normalized = _normalized_tokens(tokens)
    lowered = tuple(normalized[:2])
    single = (normalized[0],) if normalized else tuple()
    if lowered in PROJECT_COMMAND_PATTERNS or single in PROJECT_COMMAND_PATTERNS:
        if len(normalized) >= 3 and normalized[0] in {"python", "python3", "py"} and normalized[1] == "-m" and normalized[2] == "pip":
            return False
        return True
    return False


def _is_script_run(tokens: list[str]) -> bool:
    return len(tokens) >= 2 and _command_name(tokens[0]) in SCRIPT_RUNNERS and not tokens[1].startswith("-")


def _is_read_only_command(tokens: list[str]) -> bool:
    first = _command_name(tokens[0])
    if first in READ_ONLY_SINGLE_COMMANDS:
        return True
    if first == "echo" and not any(token in tokens for token in {">", ">>", "|"}) and not any(">" in token or "|" in token for token in tokens):
        return True
    if first in VERSION_COMMANDS and any(token.lower() in {"--version", "-version", "-v"} for token in tokens[1:]):
        return True
    if first in READ_ONLY_LOOKUP_COMMANDS:
        return True
    if first in READ_ONLY_PATH_COMMANDS:
        return True
    return first == "git" and len(tokens) >= 2 and tokens[1].lower() in READ_ONLY_GIT_SUBCOMMANDS


def _is_path_mutation_command(command: str, tokens: list[str]) -> bool:
    first = _command_name(tokens[0])
    if first not in MUTATION_COMMANDS:
        return False
    if first == "git":
        return _is_git_mutation(tokens[1:])
    if any(operator in command for operator in CONTROL_OPERATORS):
        return first == "echo" and "| tee" in command
    return True


def _split_command(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return []
    return [_strip_quotes(token) for token in tokens if token]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _command_name(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _normalized_tokens(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    return [_command_name(tokens[0]), *[token.lower() for token in tokens[1:]]]


def _resolve_path(raw_path: str) -> Path | None:
    if not raw_path:
        return None
    if "$" in raw_path or "%" in raw_path or "*" in raw_path or "?" in raw_path:
        return None
    try:
        return Path(raw_path).resolve()
    except Exception:
        return None


def _non_flag_paths(args: Iterable[str]) -> list[Path]:
    paths = []
    for arg in args:
        if arg.startswith("-"):
            continue
        path = _resolve_path(_strip_quotes(arg))
        if path is not None:
            paths.append(path)
    return paths


def _extract_last_non_flag_path(args: Iterable[str]) -> Path | None:
    paths = _non_flag_paths(args)
    if not paths:
        return None
    return paths[-1]


def _extract_first_non_flag_path(args: Iterable[str]) -> Path | None:
    paths = _non_flag_paths(args)
    if not paths:
        return None
    return paths[0]


def _is_git_mutation(args: list[str]) -> bool:
    if not args:
        return False
    subcommand = args[0].lower()
    if subcommand == "apply":
        return False
    if subcommand == "checkout":
        return len(args) >= 3 and args[1] == "--"
    if subcommand == "restore":
        return len(args) >= 2
    return False


def _extract_git_mutation(args: list[str]) -> tuple[AccessAction, list[Path]] | None:
    if not args:
        return None

    subcommand = args[0].lower()
    if subcommand == "checkout":
        if len(args) == 3 and args[1] == "--" and args[2] != ".":
            path = _resolve_path(args[2])
            return ("write", [path]) if path else None
        return None

    if subcommand == "restore":
        non_flag_args = [arg for arg in args[1:] if not arg.startswith("-")]
        if len(non_flag_args) == 1 and non_flag_args[0] != ".":
            path = _resolve_path(non_flag_args[0])
            return ("write", [path]) if path else None
        return None

    return None
