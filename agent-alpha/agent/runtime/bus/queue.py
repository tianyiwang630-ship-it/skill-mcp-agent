"""
Simple in-process async message bus.
"""

from __future__ import annotations

import asyncio
from typing import Union

from agent.runtime.bus.events import CronTrigger, InboundMessage, OutboundMessage


InboundEvent = Union[InboundMessage, CronTrigger]


class MessageBus:
    """Minimal inbound/outbound queue pair."""

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundEvent] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, message: InboundEvent) -> None:
        await self.inbound.put(message)

    async def consume_inbound(self) -> InboundEvent:
        return await self.inbound.get()

    async def publish_outbound(self, message: OutboundMessage) -> None:
        await self.outbound.put(message)

    async def consume_outbound(self) -> OutboundMessage:
        return await self.outbound.get()
