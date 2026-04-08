from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.runtime.bus.events import InboundMessage, OutboundMessage
from agent.runtime.bus.queue import MessageBus


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_bus_messages_expose_minimal_fields():
    inbound = InboundMessage(source="cli", target="agent", kind="user", content="hello", session_id="s1")
    outbound = OutboundMessage(source="agent", target="cli", kind="reply", content="done", session_id="s1")

    assert inbound.source == "cli"
    assert inbound.target == "agent"
    assert outbound.source == "agent"
    assert outbound.target == "cli"


@pytest.mark.anyio
async def test_message_bus_round_trips_inbound_and_outbound():
    bus = MessageBus()
    inbound = InboundMessage(source="cli", target="agent", kind="user", content="hello", session_id="s1")
    outbound = OutboundMessage(source="agent", target="cli", kind="reply", content="done", session_id="s1")

    await bus.publish_inbound(inbound)
    await bus.publish_outbound(outbound)

    assert await bus.consume_inbound() == inbound
    assert await bus.consume_outbound() == outbound
