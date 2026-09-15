"""Does cancelling the consumer of stream() stay cancelled, and does anything leak?

    .venv/bin/python docs/review/repro/repro_stream_cancel.py

Two scenarios. The first cancels the task consuming the generator, which is what Home Assistant
does when an Assist pipeline is interrupted. The second targets `_finish_sender` directly and
asks whether its `sender.cancelled()` test can swallow a cancellation that came from outside.
"""

from __future__ import annotations

import asyncio
from collections import deque
import json
import sys
from types import SimpleNamespace

from aiohttp import WSMsgType

sys.path.insert(0, "/Users/samgutentag/LABS/ha-deepgram-tts-lab/.claude/worktrees/agent-a72565c57ade8ce4a")

from custom_components.deepgram_tts.stream import FluxSocket  # noqa: E402

FRAME = b"\x01\x02" * 240


def text(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(payload))


def binary(data: bytes) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.BINARY, data=data)


class PatientSocket:
    """Never closes on its own. Emits a frame per Speak and waits forever otherwise."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.outbox: deque = deque([text({"type": "Connected", "request_id": "r"})])
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)
        await asyncio.sleep(0)
        if payload["type"] == "Speak":
            self.outbox.append(binary(FRAME))

    async def receive(self, timeout=None):
        while not self.outbox:
            await asyncio.sleep(0.005)
        return self.outbox.popleft()

    async def close(self, code=1000):
        self.closed = True


class Session:
    def __init__(self, socket) -> None:
        self.socket = socket

    def ws_connect(self, url, **kwargs):
        socket = self.socket

        class Ctx:
            async def __aenter__(self):
                return socket

            async def __aexit__(self, *exc):
                await socket.close()
                return False

        return Ctx()


async def slow_chunks(n: int, gap: float):
    for i in range(n):
        yield f"chunk {i} "
        await asyncio.sleep(gap)


async def scenario_cancel_consumer() -> None:
    socket = PatientSocket()
    flux = FluxSocket(Session(socket), "key", model="flux-haley-en")
    state: dict = {"frames": 0, "inner": None}

    async def consume() -> None:
        try:
            async for _ in flux.stream(slow_chunks(40, 0.02)):
                state["frames"] += 1
        except asyncio.CancelledError:
            state["inner"] = "CancelledError propagated out of stream()"
            raise
        except BaseException as err:  # noqa: BLE001
            state["inner"] = f"{type(err).__name__}: {err}"
            raise
        else:
            state["inner"] = "stream() returned normally"

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.12)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        outer = "OK: consumer task ended cancelled"
    else:
        outer = "BAD: consumer task ended NOT cancelled"

    await asyncio.sleep(0.05)
    live = [t for t in asyncio.all_tasks() if not t.done() and t is not asyncio.current_task()]
    print("scenario 1: cancel the task consuming stream()")
    print(f"  {outer}")
    print(f"  inner: {state['inner']}")
    print(f"  frames yielded before cancel: {state['frames']}")
    print(f"  socket closed by the async with: {socket.closed}")
    print(f"  speaks sent: {sum(1 for m in socket.sent if m['type'] == 'Speak')} of 40")
    print(f"  tasks still alive after cancel: {len(live)} {[t.get_name() for t in live]}")
    print()


async def scenario_finish_sender_swallow() -> None:
    """Can _finish_sender return normally while holding a cancellation from outside?

    The condition the code tests is `sender.cancelled()`. That says the sender task finished as
    cancelled. It does not say the CancelledError we caught came from the sender. Build the race
    directly: a sender that is already cancelled, and an outer task cancelled at the await.
    """
    flux = FluxSocket(Session(PatientSocket()), "key", model="flux-haley-en")
    result: dict = {}

    async def never() -> None:
        await asyncio.sleep(3600)

    async def outer() -> None:
        sender = asyncio.create_task(never())
        sender.cancel()
        # Let the cancellation land so sender.cancelled() is True before we await it.
        await asyncio.sleep(0.01)
        assert sender.cancelled(), "setup: sender should be cancelled"
        # Now cancel OUR task, then enter _finish_sender. The pending cancellation is
        # delivered at its first await point.
        asyncio.current_task().cancel()
        try:
            await flux._finish_sender(sender)  # noqa: SLF001
        except asyncio.CancelledError:
            result["finish"] = "re-raised CancelledError"
            raise
        else:
            result["finish"] = "returned normally, swallowing the cancellation"

    task = asyncio.create_task(outer())
    try:
        await task
    except asyncio.CancelledError:
        outcome = "OK: the cancellation survived _finish_sender"
    else:
        outcome = "BAD: _finish_sender swallowed the outer cancellation"

    print("scenario 2: _finish_sender with an already-cancelled sender and an outer cancel")
    print(f"  _finish_sender: {result.get('finish')}")
    print(f"  {outcome}")
    print(f"  task.cancelled()={task.cancelled()} task.cancelling()={task.cancelling()}")
    print()


async def main() -> None:
    print(f"python {sys.version.split()[0]}\n")
    await scenario_cancel_consumer()
    await scenario_finish_sender_swallow()


if __name__ == "__main__":
    asyncio.run(main())
