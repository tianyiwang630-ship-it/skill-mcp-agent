"""Install external skills into project or workspace skill directories."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_SKILL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
GITHUB_TREE_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)$")
GITHUB_PATH_RE = re.compile(r"^([^/\s]+)/([^/\s]+)/(.+)$")
GITHUB_REPO_URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?(?:[#?].*)?$")
GITHUB_REPO_SHORT_RE = re.compile(r"^([^/\s]+)/([^/\s]+)$")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)", re.IGNORECASE)


@dataclass(slots=True)
class SkillCandidate:
    name: str
    description: str
    relative_path: str
    install_name: str


@dataclass(slots=True)
class SkillDocument:
    relative_path: str
    content: str


@dataclass(slots=True)
class DependencyCommand:
    command: str
    kind: str
    cwd_hint: str


@dataclass(slots=True)
class SkillInspectResult:
    source: str
    kind: str
    namespace: str | None
    candidates: list[SkillCandidate]
    docs: list[SkillDocument]
    dependency_commands: list[DependencyCommand]


@dataclass(slots=True)
class SkillInstallResult:
    name: str
    scope: str
    source: str
    install_dir: Path | None
    lock_path: Path | None
    install_dirs: list[Path] = field(default_factory=list)
    namespace: str | None = None
    skills: list[str] = field(default_factory=list)
    dependency_commands: list[DependencyCommand] = field(default_factory=list)
    docs: list[SkillDocument] = field(default_factory=list)
    dry_run: bool = False


def inspect_skill_source(
    *,
    source: str,
    project_root: Path,
    name_override: str | None = None,
    namespace: str | None = None,
) -> SkillInspectResult:
    """Inspect a skill source without installing it."""
    project_root = Path(project_root).resolve()
    cache_root = project_root / "temp" / "skill-installer"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_dir = cache_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slug_for_cache(source)}"
    cache_dir.mkdir(parents=True, exist_ok=False)

    try:
        staged_dir = _stage_source(source=source, cache_dir=cache_dir, name_override=name_override)
        return _inspect_staged_source(
            staged_dir=staged_dir,
            source=source,
            name_override=name_override,
            namespace=namespace,
        )
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def install_skill(
    *,
    source: str,
    project_root: Path,
    scope: str = "project",
    workspace: Path | None = None,
    name_override: str | None = None,
    namespace: str | None = None,
    install_all: bool = False,
    with_deps: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> SkillInstallResult:
    """Install a skill from a local path, GitHub path, raw SKILL.md URL, or zip URL."""
    project_root = Path(project_root).resolve()
    workspace = Path(workspace).resolve() if workspace else project_root / "workspace"
    target_root = _target_root(project_root=project_root, workspace=workspace, scope=scope)
    cache_root = project_root / "temp" / "skill-installer"
    cache_root.mkdir(parents=True, exist_ok=True)

    cache_dir = cache_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slug_for_cache(source)}"
    cache_dir.mkdir(parents=True, exist_ok=False)

    try:
        staged_dir = _stage_source(source=source, cache_dir=cache_dir, name_override=name_override)
        inspection = _inspect_staged_source(
            staged_dir=staged_dir,
            source=source,
            name_override=name_override,
            namespace=namespace,
        )
        dependency_commands = inspection.dependency_commands if with_deps or dry_run else []
        docs = inspection.docs if with_deps or dry_run else []

        target_root.mkdir(parents=True, exist_ok=True)

        if inspection.kind == "pack":
            if not install_all and name_override is None:
                raise ValueError("Multiple SKILL.md files found. Use --name to select one skill or --all to install the pack.")
            result = _install_pack(
                staged_dir=staged_dir,
                target_root=target_root,
                scope=scope,
                source=source,
                inspection=inspection,
                force=force,
                dry_run=dry_run,
                dependency_commands=dependency_commands,
                docs=docs,
            )
        else:
            result = _install_single(
                staged_dir=staged_dir,
                target_root=target_root,
                scope=scope,
                source=source,
                inspection=inspection,
                force=force,
                dry_run=dry_run,
                dependency_commands=dependency_commands,
                docs=docs,
            )
        shutil.rmtree(cache_dir, ignore_errors=True)
        return result
    except Exception:
        raise


def list_skills(*, project_root: Path, scope: str = "all", workspace: Path | None = None) -> list[dict[str, str]]:
    project_root = Path(project_root).resolve()
    workspace = Path(workspace).resolve() if workspace else project_root / "workspace"
    roots = _scope_roots(project_root=project_root, workspace=workspace, scope=scope)
    entries: list[dict[str, str]] = []
    seen: dict[str, str] = {}

    for current_scope, root in roots:
        if not root.exists():
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            meta = parse_skill_frontmatter(skill_md)
            name = _installed_skill_name(root, skill_md, meta)
            if not meta.get("description"):
                continue
            status = "active"
            if scope == "all" and current_scope == "project" and seen.get(name) == "workspace":
                status = "overridden"
            else:
                seen[name] = current_scope
            entries.append(
                {
                    "name": name,
                    "description": meta["description"],
                    "scope": current_scope,
                    "path": str(skill_md),
                    "status": status,
                }
            )
    return entries


def _installed_skill_name(root: Path, skill_md: Path, meta: dict[str, str]) -> str:
    name = meta.get("name") or skill_md.parent.name
    try:
        relative = skill_md.relative_to(root)
    except ValueError:
        return name
    if len(relative.parts) >= 3:
        namespace = relative.parts[0]
        if VALID_SKILL_NAME.match(namespace):
            return f"{namespace}:{name}"
    return name


def remove_skill(*, project_root: Path, name: str, scope: str = "project", workspace: Path | None = None) -> Path:
    if scope == "all":
        raise ValueError("Remove requires --scope project or --scope workspace.")
    if ":" in name:
        namespace, skill_name = name.split(":", 1)
        if not VALID_SKILL_NAME.match(namespace) or not VALID_SKILL_NAME.match(skill_name):
            raise ValueError(f"Invalid skill name: {name!r}")
        path_parts = [namespace, skill_name]
    elif not VALID_SKILL_NAME.match(name):
        raise ValueError(f"Invalid skill name: {name!r}")
    else:
        path_parts = [name]

    project_root = Path(project_root).resolve()
    workspace = Path(workspace).resolve() if workspace else project_root / "workspace"
    target_root = _target_root(project_root=project_root, workspace=workspace, scope=scope)
    target = target_root.joinpath(*path_parts)
    if not target.exists():
        raise FileNotFoundError(f"Skill not found: {target}")
    shutil.rmtree(target)
    return target


def parse_skill_frontmatter(skill_file: Path) -> dict[str, str]:
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not match:
        return {}

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("\"'")
    return meta


def _target_root(*, project_root: Path, workspace: Path, scope: str) -> Path:
    if scope == "project":
        return project_root / "skills"
    if scope == "workspace":
        return workspace / "skills"
    raise ValueError("Scope must be project or workspace.")


def _scope_roots(*, project_root: Path, workspace: Path, scope: str) -> list[tuple[str, Path]]:
    roots = {
        "workspace": workspace / "skills",
        "project": project_root / "skills",
    }
    if scope == "all":
        return [("workspace", roots["workspace"]), ("project", roots["project"])]
    if scope in roots:
        return [(scope, roots[scope])]
    raise ValueError("Scope must be project, workspace, or all.")


def _stage_source(*, source: str, cache_dir: Path, name_override: str | None) -> Path:
    local_path = Path(source).expanduser()
    if local_path.exists():
        return _copy_local_source(local_path, cache_dir)

    if _is_url(source):
        parsed = urllib.parse.urlparse(source)
        if parsed.netloc.lower() == "github.com" and "/tree/" in parsed.path:
            return _download_github_tree(source, cache_dir)
        repo_match = GITHUB_REPO_URL_RE.match(source)
        if repo_match:
            owner, repo = repo_match.groups()
            return _download_github_repo(owner, repo, cache_dir)
        if parsed.path.lower().endswith(".zip"):
            return _download_zip(source, cache_dir)
        if parsed.path.endswith("SKILL.md"):
            return _download_raw_skill(source, cache_dir, name_override=name_override)
        raise ValueError("Unsupported URL. Use a GitHub tree URL, raw SKILL.md URL, or zip URL.")

    match = GITHUB_PATH_RE.match(source)
    if match:
        owner, repo, path = match.groups()
        return _download_github_directory(owner, repo, "", path, cache_dir)

    repo_match = GITHUB_REPO_SHORT_RE.match(source)
    if repo_match:
        owner, repo = repo_match.groups()
        return _download_github_repo(owner, repo, cache_dir)

    raise ValueError("Unsupported source. Use a local directory, GitHub path, raw SKILL.md URL, or zip URL.")


def _copy_local_source(source: Path, cache_dir: Path) -> Path:
    if source.is_file():
        if source.name != "SKILL.md":
            raise ValueError("Local file source must be named SKILL.md.")
        dest = cache_dir / "raw-skill"
        dest.mkdir()
        shutil.copy2(source, dest / "SKILL.md")
        return dest

    dest = cache_dir / source.name
    shutil.copytree(source, dest)
    return dest


def _download_raw_skill(source: str, cache_dir: Path, *, name_override: str | None) -> Path:
    dest = cache_dir / (name_override or "raw-skill")
    dest.mkdir()
    _download_file(source, dest / "SKILL.md")
    return dest


def _download_zip(source: str, cache_dir: Path) -> Path:
    zip_path = cache_dir / "source.zip"
    extract_dir = cache_dir / "zip"
    _download_file(source, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        _safe_extract_zip(archive, extract_dir)
    return extract_dir


def _download_github_repo(owner: str, repo: str, cache_dir: Path) -> Path:
    dest = cache_dir / repo
    dest.mkdir()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    _download_github_contents(api_url, dest)
    return dest


def _download_github_tree(source: str, cache_dir: Path) -> Path:
    match = GITHUB_TREE_RE.match(source)
    if not match:
        raise ValueError("Invalid GitHub tree URL.")
    owner, repo, ref, path = match.groups()
    return _download_github_directory(owner, repo, ref, path, cache_dir)


def _safe_extract_zip(archive: zipfile.ZipFile, extract_dir: Path) -> None:
    extract_root = extract_dir.resolve()
    for member in archive.infolist():
        target = (extract_dir / member.filename).resolve()
        if target != extract_root and extract_root not in target.parents:
            raise ValueError(f"Unsafe zip path: {member.filename}")
    archive.extractall(extract_dir)


def _download_github_directory(owner: str, repo: str, ref: str, path: str, cache_dir: Path) -> Path:
    dest = cache_dir / Path(path).name
    dest.mkdir()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{urllib.parse.quote(path.strip('/'))}"
    if ref:
        api_url += f"?ref={urllib.parse.quote(ref)}"
    _download_github_contents(api_url, dest)
    return dest


def _download_github_contents(api_url: str, dest: Path) -> None:
    payload = _read_json_url(api_url)
    if isinstance(payload, dict) and payload.get("type") == "file":
        if payload.get("name") != "SKILL.md":
            raise ValueError("GitHub file source must be SKILL.md.")
        _download_file(payload["download_url"], dest / "SKILL.md")
        return
    if not isinstance(payload, list):
        raise ValueError("GitHub source is not a directory.")

    for item in payload:
        name = item.get("name")
        if not name:
            continue
        if item.get("type") == "dir":
            child = dest / name
            child.mkdir(exist_ok=True)
            _download_github_contents(item["url"], child)
        elif item.get("type") == "file":
            _download_file(item["download_url"], dest / name)


def _inspect_staged_source(
    *,
    staged_dir: Path,
    source: str,
    name_override: str | None,
    namespace: str | None,
) -> SkillInspectResult:
    skill_files = sorted(staged_dir.rglob("SKILL.md"))
    if not skill_files:
        raise ValueError("No SKILL.md found in source.")
    all_candidates = _find_skill_candidates(staged_dir)
    if not all_candidates:
        raise ValueError("SKILL.md must include a description field in frontmatter.")

    selected = _select_candidates(staged_dir, all_candidates, name_override=name_override)
    is_pack = len(selected) > 1
    resolved_namespace = _validate_namespace(namespace or (_infer_namespace(staged_dir) if is_pack else None))
    candidates = [
        _candidate_from_skill_file(staged_dir, skill_file, namespace=resolved_namespace if is_pack else None)
        for skill_file in selected
    ]
    docs = _collect_install_docs(staged_dir)
    dependency_commands = _extract_dependency_commands(docs)

    return SkillInspectResult(
        source=source,
        kind="pack" if is_pack else "single",
        namespace=resolved_namespace,
        candidates=candidates,
        docs=docs,
        dependency_commands=dependency_commands,
    )


def _find_skill_candidates(staged_dir: Path) -> list[Path]:
    candidates = []
    for skill_file in sorted(staged_dir.rglob("SKILL.md")):
        meta = parse_skill_frontmatter(skill_file)
        if meta.get("description"):
            candidates.append(skill_file)
    return candidates


def _select_candidates(staged_dir: Path, candidates: list[Path], *, name_override: str | None) -> list[Path]:
    if name_override:
        named = [
            path
            for path in candidates
            if path.parent.name == name_override or parse_skill_frontmatter(path).get("name") == name_override
        ]
        if not named:
            raise ValueError(f"No skill named {name_override!r} found in source.")
        return [named[0]]

    direct = staged_dir / "SKILL.md"
    if direct in candidates:
        return [direct]
    return candidates


def _candidate_from_skill_file(staged_dir: Path, skill_file: Path, *, namespace: str | None) -> SkillCandidate:
    meta = parse_skill_frontmatter(skill_file)
    skill_name = meta.get("name") or skill_file.parent.name
    if not VALID_SKILL_NAME.match(skill_name):
        raise ValueError(f"Invalid skill name: {skill_name!r}")
    install_name = f"{namespace}:{skill_name}" if namespace else skill_name
    return SkillCandidate(
        name=skill_name,
        description=meta["description"],
        relative_path=_relative_posix(skill_file, staged_dir),
        install_name=install_name,
    )


def _install_single(
    *,
    staged_dir: Path,
    target_root: Path,
    scope: str,
    source: str,
    inspection: SkillInspectResult,
    force: bool,
    dry_run: bool,
    dependency_commands: list[DependencyCommand],
    docs: list[SkillDocument],
) -> SkillInstallResult:
    candidate = inspection.candidates[0]
    skill_dir = staged_dir / Path(candidate.relative_path).parent
    install_dir = target_root / candidate.name

    if not dry_run:
        _ensure_replaceable(install_dir, force=force)
        shutil.move(str(skill_dir), str(install_dir))
        lock_path = _write_lock(
            target_root=target_root,
            name=candidate.name,
            scope=scope,
            source=source,
            install_dirs=[install_dir],
            namespace=None,
            skills=[candidate.name],
            dependency_commands=dependency_commands,
            docs=docs,
        )
    else:
        lock_path = None

    return SkillInstallResult(
        name=candidate.name,
        scope=scope,
        source=source,
        install_dir=None if dry_run else install_dir,
        install_dirs=[] if dry_run else [install_dir],
        lock_path=lock_path,
        namespace=None,
        skills=[candidate.name],
        dependency_commands=dependency_commands,
        docs=docs,
        dry_run=dry_run,
    )


def _install_pack(
    *,
    staged_dir: Path,
    target_root: Path,
    scope: str,
    source: str,
    inspection: SkillInspectResult,
    force: bool,
    dry_run: bool,
    dependency_commands: list[DependencyCommand],
    docs: list[SkillDocument],
) -> SkillInstallResult:
    namespace = inspection.namespace
    if not namespace:
        raise ValueError("Skill pack installation requires a namespace.")

    install_dirs: list[Path] = []
    target_namespace_dir = target_root / namespace
    if not dry_run:
        target_namespace_dir.mkdir(parents=True, exist_ok=True)

    for candidate in inspection.candidates:
        skill_dir = staged_dir / Path(candidate.relative_path).parent
        install_dir = target_namespace_dir / candidate.name
        if not dry_run:
            _ensure_replaceable(install_dir, force=force)
            shutil.move(str(skill_dir), str(install_dir))
            install_dirs.append(install_dir)

    lock_path = None
    if not dry_run:
        lock_path = _write_lock(
            target_root=target_root,
            name=namespace,
            scope=scope,
            source=source,
            install_dirs=install_dirs,
            namespace=namespace,
            skills=[candidate.install_name for candidate in inspection.candidates],
            dependency_commands=dependency_commands,
            docs=docs,
        )

    return SkillInstallResult(
        name=namespace,
        scope=scope,
        source=source,
        install_dir=None if dry_run else target_namespace_dir,
        install_dirs=install_dirs,
        lock_path=lock_path,
        namespace=namespace,
        skills=[candidate.install_name for candidate in inspection.candidates],
        dependency_commands=dependency_commands,
        docs=docs,
        dry_run=dry_run,
    )


def _ensure_replaceable(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Skill already exists: {path}. Use --force to replace it.")
    if path.exists():
        shutil.rmtree(path)


def _infer_namespace(staged_dir: Path) -> str:
    return _sanitize_name(staged_dir.name or "skills")


def _validate_namespace(namespace: str | None) -> str | None:
    if namespace is None:
        return None
    if not VALID_SKILL_NAME.match(namespace):
        raise ValueError(f"Invalid skill namespace: {namespace!r}")
    return namespace


def _sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"skills-{cleaned}" if cleaned else "skills"
    return cleaned


def _collect_install_docs(staged_dir: Path) -> list[SkillDocument]:
    seen: set[Path] = set()
    docs: list[SkillDocument] = []
    initial = [
        path
        for path in sorted(
            staged_dir.rglob("*.md"),
            key=lambda path: (len(path.relative_to(staged_dir).parts), path.relative_to(staged_dir).as_posix()),
        )
        if path.name.lower().startswith(("readme", "install"))
    ]

    def visit(path: Path, depth: int) -> None:
        resolved = path.resolve()
        if resolved in seen or not _is_within(resolved, staged_dir.resolve()) or not path.exists():
            return
        seen.add(resolved)
        content = path.read_text(encoding="utf-8", errors="replace")
        docs.append(SkillDocument(relative_path=_relative_posix(path, staged_dir), content=content))
        if depth >= 2:
            return
        for raw_link in MARKDOWN_LINK_RE.findall(content):
            linked = _resolve_local_markdown_link(path.parent, raw_link)
            if linked is not None:
                visit(linked, depth + 1)

    for path in initial:
        visit(path, 0)
    return docs


def _resolve_local_markdown_link(base_dir: Path, raw_link: str) -> Path | None:
    parsed = urllib.parse.urlparse(raw_link.strip())
    if parsed.scheme or parsed.netloc:
        return None
    path_part = urllib.parse.unquote(parsed.path).strip()
    if not path_part:
        return None
    return (base_dir / path_part).resolve()


def _extract_dependency_commands(docs: list[SkillDocument]) -> list[DependencyCommand]:
    commands: list[DependencyCommand] = []
    seen: set[str] = set()
    for doc in docs:
        for raw_command in _iter_document_commands(doc.content):
            normalized = _normalize_dependency_command(raw_command)
            if normalized is None:
                continue
            command, kind = normalized
            if command in seen:
                continue
            seen.add(command)
            commands.append(DependencyCommand(command=command, kind=kind, cwd_hint=str(Path(doc.relative_path).parent)))
    return commands


def _iter_document_commands(content: str) -> list[str]:
    commands: list[str] = []
    in_fence = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if stripped.startswith("$ "):
            stripped = stripped[2:].strip()
        if in_fence or _normalize_dependency_command(stripped):
            if _normalize_dependency_command(stripped):
                commands.append(stripped)
    return commands


def _normalize_dependency_command(command: str) -> tuple[str, str] | None:
    stripped = command.strip()
    if _has_shell_control(stripped):
        return None
    lowered = stripped.lower()
    if lowered.startswith("uv tool install "):
        return stripped, "uv-tool"
    if lowered.startswith("uv pip install "):
        return _normalize_uv_pip_command(stripped), "uv-pip"
    if lowered.startswith("pip install "):
        return _normalize_pip_command(stripped), "uv-pip"
    if lowered.startswith(("python -m pip install ", "python3 -m pip install ", "py -m pip install ")):
        return _normalize_python_module_pip_command(stripped), "uv-pip"
    if lowered in {"npm install", "npm i"} or lowered.startswith(("npm install ", "npm i ")):
        return stripped, "node"
    if lowered == "pnpm install" or lowered.startswith(("pnpm install ", "pnpm add ")):
        return stripped, "node"
    if lowered == "yarn install" or lowered.startswith(("yarn install ", "yarn add ")):
        return stripped, "node"
    return None


def _has_shell_control(command: str) -> bool:
    return any(token in command for token in ("&&", "||", ";", "$(", "`", "\n"))


def _normalize_uv_pip_command(command: str) -> str:
    tokens = shlex.split(command, posix=False)
    lowered = [token.lower() for token in tokens]
    if "--python" in lowered:
        return command
    return _insert_python_runtime(tokens, insert_at=3)


def _normalize_pip_command(command: str) -> str:
    tokens = shlex.split(command, posix=False)
    return _insert_python_runtime(["uv", "pip", "install", *tokens[2:]], insert_at=3)


def _normalize_python_module_pip_command(command: str) -> str:
    tokens = shlex.split(command, posix=False)
    return _insert_python_runtime(["uv", "pip", "install", *tokens[4:]], insert_at=3)


def _insert_python_runtime(tokens: list[str], *, insert_at: int) -> str:
    normalized = list(tokens)
    normalized[insert_at:insert_at] = ["--python", "<AGENT_ALPHA_PYTHON>"]
    return " ".join(normalized)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _write_lock(
    *,
    target_root: Path,
    name: str,
    scope: str,
    source: str,
    install_dirs: list[Path],
    namespace: str | None,
    skills: list[str],
    dependency_commands: list[DependencyCommand],
    docs: list[SkillDocument],
) -> Path:
    lock_path = target_root / ".install-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"skills": {}}
    if lock_path.exists():
        try:
            loaded = json.loads(lock_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {"skills": {}}
    lock_entries = data.setdefault("skills", {})
    runtime_python = _runtime_python()
    lock_entries[name] = {
        "scope": scope,
        "source": source,
        "namespace": namespace,
        "skills": list(skills),
        "install_paths": [str(path) for path in install_dirs],
        "dependency_commands": [
            {"command": command.command, "kind": command.kind, "cwd_hint": command.cwd_hint}
            for command in dependency_commands
        ],
        "docs": [doc.relative_path for doc in docs],
        "runtime_python": str(runtime_python) if runtime_python else None,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
    }
    lock_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return lock_path


def _runtime_python() -> Path | None:
    import os

    raw = os.environ.get("AGENT_ALPHA_PYTHON")
    return Path(raw) if raw else None


def _download_file(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "agent-alpha-skill-installer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        dest.write_bytes(response.read())


def _read_json_url(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "agent-alpha-skill-installer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"}


def _slug_for_cache(source: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", source.strip()).strip("-")
    return (text or "skill")[:48]
