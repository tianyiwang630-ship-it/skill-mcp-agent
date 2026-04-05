from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.core.agent_loop import AgentLoop


class FakeToolFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, tool_id, name, arguments):
        self.id = tool_id
        self.function = FakeToolFunction(name, arguments)


class FakeMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeLLM:
    def __init__(self):
        self.messages_seen = []
        self._responses = [
            FakeMessage(
                content="",
                tool_calls=[FakeToolCall("call-1", "load_skill", '{"name": "pdf"}')],
            ),
            FakeMessage(content="done", tool_calls=[]),
        ]

    def generate_with_tools(self, messages, tools):
        self.messages_seen.append(messages)
        message = self._responses.pop(0)
        return type("Resp", (), {"choices": [type("Choice", (), {"message": message})()]})()


class FakeToolLoader:
    def __init__(self):
        self.calls = []

    def execute_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return '<skill name="pdf">\nUse OCR when needed.\n</skill>'


def test_agent_loop_runs_tool_then_returns_final_answer():
    history = []
    llm = FakeLLM()
    tool_loader = FakeToolLoader()
    loop = AgentLoop(
        llm=llm,
        tools=[{"type": "function", "function": {"name": "load_skill"}}],
        tool_loader=tool_loader,
        history=history,
        system_prompt="system prompt",
        max_turns=3,
    )

    result = loop.run("please help with pdf")

    assert result == "done"
    assert tool_loader.calls == [("load_skill", {"name": "pdf"})]
    assert history[0] == {"role": "user", "content": "please help with pdf"}
    assert history[-1] == {"role": "assistant", "content": "done"}
