"""
Single-agent CLI runner.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import shlex

from agent.core.agent_runtime import AgentRuntime
from agent.core.session_store import SessionKind, SessionRecord, SessionStore
from agent.core.runtime_types import RuntimeRequest
from agent.core.session_paths import create_cli_session_paths, get_default_workspace_root


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _generate_session_id() -> str:
    import uuid

    return uuid.uuid4().hex[:6]


def create_cli_session(project_root: Path) -> tuple[Path, Path, Path]:
    sessions_dir, logs_dir = create_cli_session_paths(project_root=project_root)
    workspace_root = get_default_workspace_root(project_root)
    workspace_root.mkdir(parents=True, exist_ok=True)
    return sessions_dir, logs_dir, workspace_root


def build_log_path(logs_dir: Path, session_id: str, started_at: datetime) -> Path:
    filename = f"{started_at.strftime('%Y-%m-%d_%H-%M-%S')}_session_{session_id}.json"
    return logs_dir / filename


def append_session_index(
    *,
    sessions_dir: Path,
    session_id: str,
    started_at: datetime,
    history,
    workspaces: list[Path],
    log_path: Path,
):
    index_file = sessions_dir / "index.md"
    index_file.parent.mkdir(parents=True, exist_ok=True)

    user_turns = len([message for message in history if message["role"] == "user"])
    first_msg = next((m["content"][:100] for m in history if m["role"] == "user"), "")
    first_msg = first_msg.replace("\n", " ").replace("|", "/")

    if not index_file.exists():
        header = "# Session Index\n\n"
        header += "| Session ID | Started | User Turns | Workspaces | Log File | First User Message |\n"
        header += "|---|---|---:|---|---|---|\n"
        index_file.write_text(header, encoding="utf-8")

    time_str = started_at.strftime("%m-%d %H:%M")
    project_root = sessions_dir.parent.parent

    def _display_path(path: Path) -> str:
        try:
            return str(path.relative_to(project_root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    workspace_str = "<br>".join(
        _display_path(workspace)
        for workspace in workspaces
    )
    log_str = _display_path(log_path)
    line = f"| {session_id} | {time_str} | {user_turns} | {workspace_str} | {log_str} | {first_msg} |\n"
    with open(index_file, "a", encoding="utf-8") as handle:
        handle.write(line)


def save_session_log(
    *,
    agent: AgentRuntime,
    session_id: str,
    started_at: datetime,
    sessions_dir: Path,
    workspaces: list[Path],
    log_path: Path,
):
    if not agent.history:
        print("No session history to save.")
        return

    ended_at = datetime.now()
    log_data = {
        "session_id": session_id,
        "start_time": started_at.isoformat(),
        "end_time": ended_at.isoformat(),
        "duration_seconds": (ended_at - started_at).total_seconds(),
        "total_turns": len([msg for msg in agent.history if msg["role"] == "user"]),
    }
    log_data.update(agent.get_session_log_data())

    try:
        log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved session log: {log_path}")
        append_session_index(
            sessions_dir=sessions_dir,
            session_id=session_id,
            started_at=started_at,
            history=agent.history,
            workspaces=workspaces,
            log_path=log_path,
        )
    except Exception as exc:  # pragma: no cover - logging fallback
        print(f"Failed to save session log: {exc}")


def _create_runtime(
    workspaces: list[Path],
    logs_dir: Path,
    history: list[dict] | None = None,
    permission_mode: str | None = None,
) -> AgentRuntime:
    agent = AgentRuntime(workspaces=[str(path) for path in workspaces], logs_dir=str(logs_dir))
    agent.history = [dict(message) for message in (history or [])]
    if permission_mode and agent.tool_loader.permission_manager is not None:
        agent.tool_loader.permission_manager.set_mode(permission_mode)
    return agent


def _save_session_snapshot(
    *,
    store: SessionStore,
    session_id: str,
    agent: AgentRuntime,
    workspaces: list[Path],
    created_at: datetime,
    metadata: dict | None = None,
) -> SessionRecord:
    record = SessionRecord(
        session_id=session_id,
        kind=SessionKind.INTERACTIVE,
        workspaces=[str(path) for path in workspaces],
        history=[dict(message) for message in agent.history],
        metadata=metadata or {},
        created_at=created_at.isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    return store.save(record)


def _format_session_option(index: int, record: SessionRecord) -> str:
    updated = record.updated_at.replace("T", " ")[:16]
    primary_workspace = record.workspaces[0] if record.workspaces else "(no workspace)"
    title = record.title or "(empty session)"
    return f"  [{index}] {record.session_id} | {updated} | {primary_workspace} | {title}"


def _restore_session_interactive(store: SessionStore) -> SessionRecord | None:
    sessions = store.list_recent(kind=SessionKind.INTERACTIVE)
    if not sessions:
        print("\nNo interactive sessions available to resume.\n")
        return None

    print("\nRecent sessions:")
    for index, record in enumerate(sessions, start=1):
        print(_format_session_option(index, record))
    print("  [0] cancel\n")

    choice = input("Select session: ").strip()
    if choice in {"", "0"}:
        print("Resume cancelled.\n")
        return None

    try:
        selected = int(choice)
    except ValueError:
        print("Invalid selection.\n")
        return None

    if not 1 <= selected <= len(sessions):
        print("Invalid selection.\n")
        return None

    return store.load(sessions[selected - 1].session_id)


def _print_current_workspaces(workspaces: list[Path]) -> None:
    print("\nCurrent workspaces:")
    for index, workspace in enumerate(workspaces, start=1):
        label = "primary" if index == 1 else f"extra-{index - 1}"
        print(f"  [{index}] {label}: {workspace}")
    print()


def _parse_workspace_args(raw: str) -> list[Path]:
    parts = shlex.split(raw, posix=False)
    resolved = [Path(part).expanduser().resolve() for part in parts]
    if not resolved:
        raise ValueError("Please provide at least one workspace path.")
    return resolved


def _handle_workspace_command(
    *,
    command: str,
    agent: AgentRuntime,
    logs_dir: Path,
    current_session_id: str,
    store: SessionStore,
) -> tuple[AgentRuntime, list[Path]]:
    if command in {"/workspace", "/workspace show"}:
        _print_current_workspaces(agent.workspaces)
        return agent, list(agent.workspaces)

    if command.startswith("/workspace set "):
        new_workspaces = _parse_workspace_args(command[len("/workspace set "):])
        permission_mode = (
            agent.tool_loader.permission_manager.mode
            if agent.tool_loader.permission_manager is not None
            else None
        )
        next_agent = _create_runtime(new_workspaces, logs_dir, agent.history, permission_mode)
        store.update_workspaces(
            current_session_id,
            [str(path) for path in new_workspaces],
            changed_at=datetime.now().isoformat(),
        )
        print("Updated workspaces.\n")
        _print_current_workspaces(new_workspaces)
        return next_agent, new_workspaces

    if command.startswith("/workspace add "):
        additions = _parse_workspace_args(command[len("/workspace add "):])
        merged = list(agent.workspaces)
        for workspace in additions:
            if workspace not in merged:
                merged.append(workspace)
        permission_mode = (
            agent.tool_loader.permission_manager.mode
            if agent.tool_loader.permission_manager is not None
            else None
        )
        next_agent = _create_runtime(merged, logs_dir, agent.history, permission_mode)
        store.update_workspaces(
            current_session_id,
            [str(path) for path in merged],
            changed_at=datetime.now().isoformat(),
        )
        print("Added workspace.\n")
        _print_current_workspaces(merged)
        return next_agent, merged

    print(
        "\nWorkspace commands:\n"
        "  /workspace\n"
        "  /workspace show\n"
        "  /workspace set <path1> [<path2> ...]\n"
        "  /workspace add <path1> [<path2> ...]\n"
    )
    return agent, list(agent.workspaces)


def run_single_agent_cli():
    print("=" * 70)
    print("Agent CLI")
    print("=" * 70)

    project_root = PROJECT_ROOT.resolve()
    session_id = _generate_session_id()
    started_at = datetime.now()
    sessions_dir, logs_dir, workspace_root = create_cli_session(project_root)
    log_path = build_log_path(logs_dir, session_id, started_at)
    session_store = SessionStore(sessions_dir)
    current_workspaces = [workspace_root]
    agent = _create_runtime(current_workspaces, logs_dir)
    _save_session_snapshot(
        store=session_store,
        session_id=session_id,
        agent=agent,
        workspaces=current_workspaces,
        created_at=started_at,
        metadata={"project_root": str(project_root)},
    )

    print("\nCommands:")
    print("  - quit / exit: save the session log and leave")
    print("  - reset: clear current history")
    print("  - /resume: restore an earlier interactive session")
    print("  - /workspace: show current workspaces")
    print("  - /workspace set <path1> [<path2> ...]: replace workspaces")
    print("  - /workspace add <path1> [<path2> ...]: append workspaces")
    print("  - context: print current prompt + history JSON")
    print("  - save: write current context JSON into this session temp directory")
    print("  - save-log: persist the session log now")
    print("  - /admin: change permission mode")
    print("  - press ESC twice: interrupt the current model/tool turn\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                save_session_log(
                    agent=agent,
                    session_id=session_id,
                    started_at=started_at,
                    sessions_dir=sessions_dir,
                    workspaces=current_workspaces,
                    log_path=log_path,
                )
                break

            if user_input.lower() == "reset":
                agent.reset()
                _save_session_snapshot(
                    store=session_store,
                    session_id=session_id,
                    agent=agent,
                    workspaces=current_workspaces,
                    created_at=started_at,
                    metadata={"project_root": str(project_root)},
                )
                continue

            if user_input.lower() == "/resume":
                if agent.history:
                    _save_session_snapshot(
                        store=session_store,
                        session_id=session_id,
                        agent=agent,
                        workspaces=current_workspaces,
                        created_at=started_at,
                        metadata={"project_root": str(project_root)},
                    )

                record = _restore_session_interactive(session_store)
                if record is None:
                    continue

                session_id = record.session_id
                started_at = datetime.fromisoformat(record.created_at)
                current_workspaces = [
                    Path(workspace).expanduser().resolve() for workspace in (record.workspaces or [workspace_root])
                ]
                permission_mode = (
                    agent.tool_loader.permission_manager.mode
                    if agent.tool_loader.permission_manager is not None
                    else None
                )
                agent.close()
                agent = _create_runtime(current_workspaces, logs_dir, record.history, permission_mode)
                log_path = build_log_path(logs_dir, session_id, datetime.now())
                print(f"Resumed session {session_id}.\n")
                _print_current_workspaces(current_workspaces)
                continue

            if user_input.lower().startswith("/workspace"):
                try:
                    next_agent, next_workspaces = _handle_workspace_command(
                        command=user_input,
                        agent=agent,
                        logs_dir=logs_dir,
                        current_session_id=session_id,
                        store=session_store,
                    )
                except ValueError as exc:
                    print(f"\nError: {exc}\n")
                    continue

                if next_agent is not agent:
                    agent.close()
                    agent = next_agent
                    current_workspaces = next_workspaces
                    _save_session_snapshot(
                        store=session_store,
                        session_id=session_id,
                        agent=agent,
                        workspaces=current_workspaces,
                        created_at=started_at,
                        metadata={"project_root": str(project_root)},
                    )
                continue

            if user_input.lower() == "context":
                print("\n" + "=" * 70)
                print(agent.get_context_json())
                print("=" * 70 + "\n")
                continue

            if user_input.lower() == "save":
                save_path = agent.workspace_root / "agent_context.json"
                agent.save_context(str(save_path))
                continue

            if user_input.lower() == "save-log":
                save_session_log(
                    agent=agent,
                    session_id=session_id,
                    started_at=started_at,
                    sessions_dir=sessions_dir,
                    workspaces=current_workspaces,
                    log_path=log_path,
                )
                continue

            if user_input.lower() == "/admin":
                _handle_admin(agent)
                continue

            response = agent.handle(RuntimeRequest(content=user_input, session_id=session_id))
            print(f"\nAgent: {response.content}\n")
            _save_session_snapshot(
                store=session_store,
                session_id=session_id,
                agent=agent,
                workspaces=current_workspaces,
                created_at=started_at,
                metadata={"project_root": str(project_root)},
            )
        except KeyboardInterrupt:
            print("\n\nInterrupted by Ctrl+C.")
            save_session_log(
                agent=agent,
                session_id=session_id,
                started_at=started_at,
                sessions_dir=sessions_dir,
                workspaces=current_workspaces,
                log_path=log_path,
            )
            agent.close()
            break
        except Exception as exc:
            print(f"\nError: {exc}")
            import traceback

            traceback.print_exc()
            print()


def _handle_admin(agent: AgentRuntime):
    permission_manager = agent.tool_loader.permission_manager
    if permission_manager is None:
        print("\nPermissions are disabled.\n")
        return

    print("\n" + "=" * 70)
    print("Permission Mode")
    print("=" * 70)
    print(f"\nCurrent mode: {permission_manager.mode}")
    print("\nOptions:")
    print("  [1] ask - ask before risky actions")
    print("  [2] auto - auto-approve allowed actions")
    print("  [0] cancel")
    print("=" * 70)

    choice = input("Select (1/2/0): ").strip()
    if choice == "1":
        permission_manager.set_mode("ask")
    elif choice == "2":
        permission_manager.set_mode("auto")
    elif choice == "0":
        print("No changes made.")
    else:
        print("Invalid choice.")
    print()


if __name__ == "__main__":
    run_single_agent_cli()
