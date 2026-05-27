"""Install external skills into project or workspace skill directories."""

from __future__ import annotations

import json
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_SKILL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
GITHUB_TREE_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)$")
GITHUB_PATH_RE = re.compile(r"^([^/\s]+)/([^/\s]+)/(.+)$")


@dataclass(slots=True)
class SkillInstallResult:
    name: str
    scope: str
    source: str
    install_dir: Path
    lock_path: Path


def install_skill(
    *,
    source: str,
    project_root: Path,
    scope: str = "project",
    workspace: Path | None = None,
    name_override: str | None = None,
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
        skill_dir, meta = _validate_staged_skill(staged_dir, name_override=name_override)
        skill_name = name_override or meta.get("name") or skill_dir.name
        if not skill_name or not VALID_SKILL_NAME.match(skill_name):
            raise ValueError(f"Invalid skill name: {skill_name!r}")
        if not meta.get("description"):
            raise ValueError("SKILL.md must include a description field in frontmatter.")

        target_root.mkdir(parents=True, exist_ok=True)
        install_dir = target_root / skill_name
        if install_dir.exists() and not force:
            raise FileExistsError(f"Skill already exists: {install_dir}. Use --force to replace it.")
        if install_dir.exists():
            shutil.rmtree(install_dir)

        shutil.move(str(skill_dir), str(install_dir))
        lock_path = _write_lock(
            target_root=target_root,
            name=skill_name,
            scope=scope,
            source=source,
            install_dir=install_dir,
        )
        shutil.rmtree(cache_dir, ignore_errors=True)
        return SkillInstallResult(
            name=skill_name,
            scope=scope,
            source=source,
            install_dir=install_dir,
            lock_path=lock_path,
        )
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
            name = meta.get("name") or skill_md.parent.name
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


def remove_skill(*, project_root: Path, name: str, scope: str = "project", workspace: Path | None = None) -> Path:
    if scope == "all":
        raise ValueError("Remove requires --scope project or --scope workspace.")
    if not VALID_SKILL_NAME.match(name):
        raise ValueError(f"Invalid skill name: {name!r}")

    project_root = Path(project_root).resolve()
    workspace = Path(workspace).resolve() if workspace else project_root / "workspace"
    target_root = _target_root(project_root=project_root, workspace=workspace, scope=scope)
    target = target_root / name
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
        if parsed.path.lower().endswith(".zip"):
            return _download_zip(source, cache_dir)
        if parsed.path.endswith("SKILL.md"):
            return _download_raw_skill(source, cache_dir, name_override=name_override)
        raise ValueError("Unsupported URL. Use a GitHub tree URL, raw SKILL.md URL, or zip URL.")

    match = GITHUB_PATH_RE.match(source)
    if match:
        owner, repo, path = match.groups()
        return _download_github_directory(owner, repo, "", path, cache_dir)

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
        archive.extractall(extract_dir)
    return extract_dir


def _download_github_tree(source: str, cache_dir: Path) -> Path:
    match = GITHUB_TREE_RE.match(source)
    if not match:
        raise ValueError("Invalid GitHub tree URL.")
    owner, repo, ref, path = match.groups()
    return _download_github_directory(owner, repo, ref, path, cache_dir)


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


def _validate_staged_skill(staged_dir: Path, *, name_override: str | None) -> tuple[Path, dict[str, str]]:
    candidates = sorted(staged_dir.rglob("SKILL.md"))
    if not candidates:
        raise ValueError("No SKILL.md found in source.")

    if name_override:
        named = [
            path
            for path in candidates
            if path.parent.name == name_override or parse_skill_frontmatter(path).get("name") == name_override
        ]
        skill_file = named[0] if named else candidates[0]
    elif len(candidates) == 1:
        skill_file = candidates[0]
    else:
        direct = staged_dir / "SKILL.md"
        if direct.exists():
            skill_file = direct
        else:
            raise ValueError("Multiple SKILL.md files found. Use --name to select the target skill.")

    meta = parse_skill_frontmatter(skill_file)
    if not meta.get("name") and name_override is None and skill_file.parent.name == "raw-skill":
        raise ValueError("Raw SKILL.md sources must include a name field or use --name.")
    return skill_file.parent, meta


def _write_lock(*, target_root: Path, name: str, scope: str, source: str, install_dir: Path) -> Path:
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
    skills = data.setdefault("skills", {})
    skills[name] = {
        "scope": scope,
        "source": source,
        "install_path": str(install_dir),
        "installed_at": datetime.now().isoformat(timespec="seconds"),
    }
    lock_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return lock_path


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
