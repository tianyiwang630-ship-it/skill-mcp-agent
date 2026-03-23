"""
Single-agent CLI runner.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent.core.core_agent import Agent
from agent.core.session_paths import create_cli_session_paths


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _generate_session_id() -> str:
    import uuid

    return uuid.uuid4().hex[:6]


def create_cli_session(workspace_root: Path, session_id: str) -> tuple[Path, Path]:
    return create_cli_session_paths(workspace_root=workspace_root, session_id=session_id)


def build_log_path(logs_dir: Path, session_id: str, started_at: datetime) -> Path:
    filename = f"{started_at.strftime('%Y-%m-%d_%H-%M-%S')}_session_{session_id}.json"
    return logs_dir / filename


def append_session_index(
    *,
    workspace_root: Path,
    session_id: str,
    started_at: datetime,
    history,
    session_workspace: Path,
    log_path: Path,
):
    index_file = workspace_root / "sessions" / "index.md"
    index_file.parent.mkdir(parents=True, exist_ok=True)

    user_turns = len([message for message in history if message["role"] == "user"])
    first_msg = next((m["content"][:100] for m in history if m["role"] == "user"), "")
    first_msg = first_msg.replace("\n", " ").replace("|", "/")

    if not index_file.exists():
        header = "# Session Index\n\n"
        header += "| Session ID | Started | User Turns | Workspace | Log File | First User Message |\n"
        header += "|---|---|---:|---|---|---|\n"
        index_file.write_text(header, encoding="utf-8")

    time_str = started_at.strftime("%m-%d %H:%M")
    workspace_str = str(session_workspace.relative_to(workspace_root)).replace("\\", "/")
    log_str = str(log_path.relative_to(workspace_root)).replace("\\", "/")
    line = f"| {session_id} | {time_str} | {user_turns} | {workspace_str} | {log_str} | {first_msg} |\n"
    with open(index_file, "a", encoding="utf-8") as handle:
        handle.write(line)


def save_session_log(
    *,
    agent: Agent,
    session_id: str,
    started_at: datetime,
    workspace_root: Path,
    session_workspace: Path,
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
            workspace_root=workspace_root,
            session_id=session_id,
            started_at=started_at,
            history=agent.history,
            session_workspace=session_workspace,
            log_path=log_path,
        )
    except Exception as exc:  # pragma: no cover - logging fallback
        print(f"Failed to save session log: {exc}")


def run_single_agent_cli():
    print("=" * 70)
    print("Agent CLI")
    print("=" * 70)

    workspace_root = PROJECT_ROOT.resolve()
    session_id = _generate_session_id()
    started_at = datetime.now()
    session_workspace, logs_dir = create_cli_session(workspace_root, session_id)
    log_path = build_log_path(logs_dir, session_id, started_at)

    agent = Agent(workspace_root=str(session_workspace), logs_dir=str(logs_dir))

    print("\nCommands:")
    print("  - quit / exit: save the session log and leave")
    print("  - reset: clear current history")
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
                    workspace_root=workspace_root,
                    session_workspace=session_workspace,
                    log_path=log_path,
                )
                break

            if user_input.lower() == "reset":
                agent.reset()
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
                    workspace_root=workspace_root,
                    session_workspace=session_workspace,
                    log_path=log_path,
                )
                continue

            if user_input.lower() == "/admin":
                _handle_admin(agent)
                continue

            response = agent.run(user_input)
            print(f"\nAgent: {response}\n")
        except KeyboardInterrupt:
            print("\n\nInterrupted by Ctrl+C.")
            save_session_log(
                agent=agent,
                session_id=session_id,
                started_at=started_at,
                workspace_root=workspace_root,
                session_workspace=session_workspace,
                log_path=log_path,
            )
            mcp_mgr = agent.tool_loader.tool_executors.get("_mcp_manager")
            if mcp_mgr:
                try:
                    mcp_mgr.close_all()
                except Exception:
                    pass
            break
        except Exception as exc:
            print(f"\nError: {exc}")
            import traceback

            traceback.print_exc()
            print()


def _handle_admin(agent: Agent):
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
