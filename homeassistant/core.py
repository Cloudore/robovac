"""Minimal Home Assistant core stubs."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Coroutine


class HomeAssistant:
    """Very small subset of the Home Assistant core object."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        try:
            # Use the running event loop when tests execute inside an async context
            self.loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - fallback for sync contexts
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    async def async_add_executor_job(self, func: Callable[..., Any], *args: Any) -> Any:
        return await self.loop.run_in_executor(None, func, *args)

    async def async_block_till_done(self) -> None:
        """Advance the event loop until pending callbacks complete."""

        # Yield to the event loop a few times to let callbacks schedule work
        for _ in range(3):
            await asyncio.sleep(0)

        # Await any pending tasks to make sure queued jobs complete before
        # tests assert on side effects. This mirrors Home Assistant's
        # behaviour closely enough for the integration test-suite.
        pending = [
            task
            for task in asyncio.all_tasks()
            if not task.done() and task is not asyncio.current_task()
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


def callback(func: Callable[..., Any]) -> Callable[..., Any]:  # pragma: no cover - simple passthrough
    return func
