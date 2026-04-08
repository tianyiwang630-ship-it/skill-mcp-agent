import asyncio
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.runtime.bus.events import CronTrigger
from agent.runtime.bus.queue import MessageBus
from agent.runtime.cron.service import CronService
from agent.runtime.cron.types import CronJob


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_cron_service_publishes_trigger_to_bus():
    bus = MessageBus()
    service = CronService(bus=bus)
    job = CronJob(job_id="job-1", name="daily", content="run daily check", session_id="cron:daily")

    await service.trigger(job)

    trigger = await bus.consume_inbound()
    assert isinstance(trigger, CronTrigger)
    assert trigger.job_id == "job-1"
    assert trigger.content == "run daily check"


@pytest.mark.anyio
async def test_cron_service_does_not_call_runtime_directly():
    bus = MessageBus()
    service = CronService(bus=bus)
    job = CronJob(job_id="job-2", name="hourly", content="run hourly check", session_id="cron:hourly")

    await service.trigger(job)

    trigger = await asyncio.wait_for(bus.consume_inbound(), timeout=1)
    assert trigger.target == "agent"
