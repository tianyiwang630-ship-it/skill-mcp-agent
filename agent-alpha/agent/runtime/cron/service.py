"""
Minimal cron trigger service.
"""

from __future__ import annotations

from agent.runtime.bus.events import CronTrigger
from agent.runtime.bus.queue import MessageBus
from agent.runtime.cron.types import CronJob


class CronService:
    """Small service that emits cron triggers onto the message bus."""

    def __init__(self, *, bus: MessageBus):
        self.bus = bus

    async def trigger(self, job: CronJob) -> None:
        trigger = CronTrigger(
            job_id=job.job_id,
            content=job.content,
            session_id=job.session_id,
            target=job.target,
            metadata={"job_name": job.name, **job.metadata},
        )
        await self.bus.publish_inbound(trigger)
