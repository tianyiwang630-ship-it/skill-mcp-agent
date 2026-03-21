"""
Single-agent CLI runner.
"""

from __future__ import annotations

from agent.core.core_agent import Agent


def run_single_agent_cli():
    print("=" * 70)
    print("Agent CLI")
    print("=" * 70)

    agent = Agent()

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
                agent.save_session_log()
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
                save_path = agent.temp_dir / "agent_context.json"
                agent.save_context(str(save_path))
                continue

            if user_input.lower() == "save-log":
                agent.save_session_log()
                continue

            if user_input.lower() == "/admin":
                _handle_admin(agent)
                continue

            response = agent.run(user_input)
            print(f"\nAgent: {response}\n")
        except KeyboardInterrupt:
            print("\n\nInterrupted by Ctrl+C.")
            agent.save_session_log()
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
