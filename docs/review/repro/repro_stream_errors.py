"""Reproductions for stream.py error typing and cleanup. Run with the repo .venv python.

    .venv/bin/python docs/review/repro/repro_stream_errors.py

Each check prints OBSERVED with what actually happened. Nothing here asserts; the output is
the evidence.
"""

from __future__ import annotations

import asyncio
from collections import deque
import gc
import json
import sys
from types import SimpleNamespace

from aiohttp import ClientError, WSMsgType, WSServerHandshakeError
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

sys.path.insert(0, "/Users/samgutentag/LABS/ha-deepgram-tts-lab/.claude/worktrees/agent-a72565c57ade8ce4a")

from custom_components.deepgram_tts.errors import (  # noqa: E402
    DeepgramAuthError,
    DeepgramConnectionError,
)
from custom_components.deepgram_tts.stream import FluxSocket  # noqa: E402

FRAME = b"\x01\x02" * 240


def text(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(payload))


def raw_text(data: str) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.TEXT, data=data)


def binary(data: bytes) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.BINARY, data=data)


CLOSED = SimpleNamespace(type=WSMsgType.CLOSED, data=None)


class FakeSocket:
    """Scriptable socket. `script` maps a sent message type to messages to enqueue."""

    def __init__(self, *, connected=True, on_speak=None, on_flush=None, frames=1):
        self.sent: list[dict] = []
        self.outbox: deque = deque()
        self.closed = False
        self.close_calls = 0
        self._on_speak = on_speak
        self._on_flush = on_flush
        self._frames = frames
        self._started = False
        self.outbox.append(
            text({"type": "Connected", "request_id": "req-1"}) if connected else CLOSED
        )

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)
        await asyncio.sleep(0)
        if payload["type"] == "Speak":
            if self._on_speak is not None:
                self.outbox.extend(self._on_speak)
                return
            if not self._started:
                self.outbox.append(text({"type": "SpeechStarted", "speech_id": "s-1"}))
                self._started = True
            for _ in range(self._frames):
                self.outbox.append(binary(FRAME))
        elif payload["type"] == "Flush" and self._on_flush is not None:
            self.outbox.extend(self._on_flush)

    async def receive(self, timeout=None):
        for _ in range(500):
            if self.outbox:
                return self.outbox.popleft()
            await asyncio.sleep(0)
        return CLOSED

    async def close(self, code=1000):
        self.close_calls += 1
        self.closed = True


class FakeSession:
    def __init__(self, socket=None, raises=None):
        self.socket = socket or FakeSocket()
        self.raises = raises
        self.aexit_calls = 0

    def ws_connect(self, url, **kwargs):
        session = self

        class Ctx:
            async def __aenter__(self):
                if session.raises:
                    raise session.raises
                return session.socket

            async def __aexit__(self, *exc):
                # The real aiohttp context manager closes the socket here.
                session.aexit_calls += 1
                await session.socket.close()
                return False

        return Ctx()


async def chunks(*items, gap: float = 0.0):
    for item in items:
        yield item
        await asyncio.sleep(gap)


def report(name: str, detail: str) -> None:
    print(f"OBSERVED  {name}\n          {detail}\n")


# --- 1. a rejected API key during the websocket handshake -------------------------------


async def check_handshake_401() -> None:
    """A bad key on wss:// is an HTTP 401 on the upgrade, not an in-band Error frame."""
    err = WSServerHandshakeError(
        SimpleNamespace(real_url=URL("wss://api.deepgram.com/v2/speak")),
        (),
        status=401,
        message="Invalid credentials",
        headers=CIMultiDictProxy(CIMultiDict()),
    )
    socket = FluxSocket(FakeSession(raises=err), "expired-key", model="flux-haley-en")
    try:
        async for _ in socket.stream(chunks("hi.")):
            pass
    except BaseException as caught:  # noqa: BLE001
        report(
            "handshake 401 -> exception type",
            f"{type(caught).__name__}: {caught}\n"
            f"          is DeepgramAuthError?       {isinstance(caught, DeepgramAuthError)}\n"
            f"          is DeepgramConnectionError? {isinstance(caught, DeepgramConnectionError)}",
        )


# --- 2. audio_duration_ms arriving as a string -------------------------------------------


async def check_string_duration() -> None:
    socket = FluxSocket(
        FakeSession(
            FakeSocket(
                on_flush=[
                    text(
                        {
                            "type": "SpeechMetadata",
                            "speech_id": "s-1",
                            "audio_duration_ms": "10",
                        }
                    )
                ]
            )
        ),
        "key",
        model="flux-haley-en",
    )
    try:
        frames = [f async for f in socket.stream(chunks("hi."))]
    except BaseException as caught:  # noqa: BLE001
        report(
            'audio_duration_ms = "10" (a string)',
            f"{type(caught).__name__}: {caught}\n"
            f"          typed as a Deepgram error? "
            f"{isinstance(caught, (DeepgramAuthError, DeepgramConnectionError))}",
        )
    else:
        report('audio_duration_ms = "10"', f"no exception, {len(frames)} frames")


async def check_zero_duration() -> None:
    socket = FluxSocket(
        FakeSession(
            FakeSocket(
                frames=20,
                on_flush=[
                    text({"type": "SpeechMetadata", "speech_id": "s-1", "audio_duration_ms": 0})
                ],
            )
        ),
        "key",
        model="flux-haley-en",
    )
    frames = [f async for f in socket.stream(chunks("hi."))]
    report(
        "audio_duration_ms = 0 with 9600 bytes of audio",
        f"frames={len(frames)} audio_bytes={socket.metrics.audio_bytes} "
        f"warnings={socket.metrics.warnings}",
    )


# --- 3. a malformed text frame -----------------------------------------------------------


async def check_bad_json() -> None:
    socket = FluxSocket(
        FakeSession(FakeSocket(on_speak=[raw_text("<html>502 Bad Gateway</html>")])),
        "key",
        model="flux-haley-en",
    )
    try:
        async for _ in socket.stream(chunks("hi.")):
            pass
    except BaseException as caught:  # noqa: BLE001
        report(
            "server sends a non-JSON text frame",
            f"{type(caught).__name__}: {caught}\n"
            f"          typed as a Deepgram error? "
            f"{isinstance(caught, (DeepgramAuthError, DeepgramConnectionError))}",
        )


async def check_json_not_an_object() -> None:
    socket = FluxSocket(
        FakeSession(FakeSocket(on_speak=[raw_text('["SpeechStarted"]')])),
        "key",
        model="flux-haley-en",
    )
    try:
        async for _ in socket.stream(chunks("hi.")):
            pass
    except BaseException as caught:  # noqa: BLE001
        report(
            "server sends valid JSON that is not an object",
            f"{type(caught).__name__}: {caught}\n"
            f"          typed as a Deepgram error? "
            f"{isinstance(caught, (DeepgramAuthError, DeepgramConnectionError))}",
        )


# --- 4. the consumer abandons the generator early ----------------------------------------


async def check_abandon_with_aclose() -> None:
    """What Home Assistant does when a pipeline is interrupted: stop consuming."""
    session = FakeSession(FakeSocket(frames=1))
    socket = FluxSocket(session, "key", model="flux-haley-en")

    agen = socket.stream(chunks("one ", "two ", "three ", "four ", "five.", gap=0.01))
    seen = 0
    async for _frame in agen:
        seen += 1
        if seen == 2:  # header plus one audio frame, then walk away
            break

    tasks_before = {t for t in asyncio.all_tasks() if not t.done()}
    await agen.aclose()
    await asyncio.sleep(0.05)
    leaked = [
        t
        for t in asyncio.all_tasks()
        if not t.done() and t is not asyncio.current_task() and t in tasks_before
    ]
    report(
        "consumer breaks then calls aclose()",
        f"frames consumed={seen} socket.closed={session.socket.closed} "
        f"aexit_calls={session.aexit_calls}\n"
        f"          chunks_sent={socket.metrics.chunks_sent} leaked tasks={len(leaked)}\n"
        f"          sample-rate self check ran? warnings={socket.metrics.warnings} "
        f"audio_duration_ms={socket.metrics.audio_duration_ms}",
    )


async def check_abandon_without_aclose() -> None:
    """Drop the reference instead of closing it, which is what a `break` alone does."""
    session = FakeSession(FakeSocket(frames=1))
    socket = FluxSocket(session, "key", model="flux-haley-en")

    agen = socket.stream(chunks("one ", "two ", "three ", "four ", "five.", gap=0.01))
    seen = 0
    async for _frame in agen:
        seen += 1
        if seen == 2:
            break

    del agen
    gc.collect()
    await asyncio.sleep(0.05)
    live = [t for t in asyncio.all_tasks() if not t.done() and t is not asyncio.current_task()]
    report(
        "consumer breaks and drops the generator (no aclose)",
        f"socket.closed={session.socket.closed} aexit_calls={session.aexit_calls} "
        f"live tasks={len(live)}\n          {[t.get_coro().__qualname__ for t in live]}",
    )


async def check_consumer_task_cancelled() -> None:
    """The realistic interruption: the task consuming the generator gets cancelled."""
    session = FakeSession(FakeSocket(frames=1))
    socket = FluxSocket(session, "key", model="flux-haley-en")
    state: dict = {"frames": 0, "outcome": None}

    async def consume() -> None:
        try:
            async for _ in socket.stream(
                chunks("one ", "two ", "three ", "four ", "five.", gap=0.02)
            ):
                state["frames"] += 1
        except asyncio.CancelledError:
            state["outcome"] = "CancelledError propagated"
            raise
        except BaseException as err:  # noqa: BLE001
            state["outcome"] = f"{type(err).__name__}: {err}"
            raise
        else:
            state["outcome"] = "ran to completion despite cancellation"

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.03)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        outer = "consumer task ended cancelled"
    else:
        outer = "consumer task ended NOT cancelled (cancellation was swallowed)"
    await asyncio.sleep(0.05)
    live = [t for t in asyncio.all_tasks() if not t.done() and t is not asyncio.current_task()]
    report(
        "consumer task is cancelled mid stream",
        f"{outer}; inner={state['outcome']}; frames={state['frames']}\n"
        f"          socket.closed={session.socket.closed} live tasks={len(live)}",
    )


# --- 5. more than one SpeechMetadata in a turn -------------------------------------------


async def check_two_speech_segments() -> None:
    """If the server segments a turn, _receive returns at the first SpeechMetadata."""
    socket = FakeSocket(frames=1)
    # Server behavior under test: it finishes speech 1 while text is still arriving.
    socket._on_speak = [  # noqa: SLF001
        text({"type": "SpeechStarted", "speech_id": "s-1"}),
        binary(FRAME),
        text({"type": "SpeechMetadata", "speech_id": "s-1", "audio_duration_ms": 10}),
        text({"type": "SpeechStarted", "speech_id": "s-2"}),
        binary(FRAME),
        binary(FRAME),
    ]
    flux = FluxSocket(FakeSession(socket), "key", model="flux-haley-en")
    frames = [f async for f in flux.stream(chunks("one ", "two ", "three.", gap=0.01))]
    audio = b"".join(frames[1:])
    report(
        "server emits SpeechMetadata for segment 1, then segment 2",
        f"audio frames yielded={len(frames) - 1} bytes={len(audio)} "
        f"(3 frames of audio were available)\n"
        f"          chunks_sent={flux.metrics.chunks_sent} of 3  "
        f"warnings={flux.metrics.warnings}",
    )


# --- 6. no overall bound on a turn -------------------------------------------------------


async def check_no_total_timeout() -> None:
    """Each receive() gets a fresh timeout, so a chatty server is unbounded."""
    class Dribbler(FakeSocket):
        def __init__(self):
            super().__init__()
            self.receives = 0

        async def receive(self, timeout=None):
            self.receives += 1
            if self.outbox:
                return self.outbox.popleft()
            if self.receives > 400:
                return CLOSED
            await asyncio.sleep(0)
            return text({"type": "Warning", "code": "W", "description": "still here"})

    socket = Dribbler()
    flux = FluxSocket(FakeSession(socket), "key", model="flux-haley-en")
    try:
        async for _ in flux.stream(chunks("hi.")):
            pass
    except BaseException as caught:  # noqa: BLE001
        report(
            "server dribbles Warning frames forever",
            f"receive() calls before it ended={socket.receives}, "
            f"warnings recorded={len(flux.metrics.warnings)}\n"
            f"          ended only because the fake gave up: "
            f"{type(caught).__name__}: {caught}\n"
            f"          nothing in the client bounds total turn time",
        )


async def main() -> None:
    print(f"python {sys.version.split()[0]}\n")
    for check in (
        check_handshake_401,
        check_string_duration,
        check_zero_duration,
        check_bad_json,
        check_json_not_an_object,
        check_abandon_with_aclose,
        check_abandon_without_aclose,
        check_consumer_task_cancelled,
        check_two_speech_segments,
        check_no_total_timeout,
    ):
        try:
            await check()
        except Exception as err:  # noqa: BLE001
            print(f"REPRO ERROR in {check.__name__}: {type(err).__name__}: {err}\n")


if __name__ == "__main__":
    asyncio.run(main())
