"""Ephemeral per-run event fanout for the dashboard's server-sent event stream."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

_subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)


def subscribe(run_id: UUID) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers[str(run_id)].add(queue)
    return queue


def unsubscribe(run_id: UUID, queue: asyncio.Queue[dict[str, Any]]) -> None:
    key = str(run_id)
    listeners = _subscribers.get(key)
    if listeners is None:
        return
    listeners.discard(queue)
    if not listeners:
        _subscribers.pop(key, None)


async def publish(run_id: UUID, event: dict[str, Any]) -> None:
    """Fan out one ephemeral UI event; dashboard dialogue is not persisted to audit."""
    key = str(run_id)
    envelope = {"run_id": key, **event}
    for queue in tuple(_subscribers.get(key, ())):
        queue.put_nowait(envelope)
