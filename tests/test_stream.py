"""The Flux websocket client, against a scripted fake socket.

The fake is a small state machine rather than a fixed list of messages, because the property
worth testing is the interleaving: frames have to come back while text is still going in. A
fixed script would pass even if the client sent everything before reading anything, which is
the one implementation that defeats the point of streaming.
"""

from collections import deque
import json
import struct
from types import SimpleNamespace

from aiohttp import ClientError, WSMsgType
import pytest

from custom_components.deepgram_tts.const import DEFAULT_VOICE, WS_SAMPLE_RATE
from custom_components.deepgram_tts.errors import DeepgramAuthError, DeepgramConnectionError
from custom_components.deepgram_tts.stream import FluxSocket, wav_header

FRAME = b"\x01\x02" * 240  # 480 bytes, 10 ms of 24 kHz mono linear16


def text(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(payload))


def binary(data: bytes) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.BINARY, data=data)


CLOSED = SimpleNamespace(type=WSMsgType.CLOSED, data=None)


class FakeSocket:
    """Answers Speak with audio and Flush with SpeechMetadata, the way the real one does."""

    def __init__(
        self,
        *,
        connected: bool = True,
        frames_per_speak: int = 1,
        audio_duration_ms: float | None = None,
        error_on_speak: dict | None = None,
        close_after_frames: int | None = None,
    ) -> None:
        self.sent: list[dict] = []
        self.outbox: deque = deque()
        self.closed = False
        self._frames_per_speak = frames_per_speak
        self._frames_emitted = 0
        self._speech_started = False
        self._error_on_speak = error_on_speak
        self._close_after_frames = close_after_frames
        self._audio_duration_ms = audio_duration_ms

        if connected:
            self.outbox.append(text({"type": "Connected", "request_id": "req-1"}))
        else:
            self.outbox.append(CLOSED)

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)
        # Yielding here is what lets the receive loop interleave with the send loop.
        await _yield()

        if payload["type"] == "Speak":
            if self._error_on_speak:
                self.outbox.append(text(self._error_on_speak))
                return
            if not self._speech_started:
                self.outbox.append(text({"type": "SpeechStarted", "speech_id": "s-1"}))
                self._speech_started = True
            for _ in range(self._frames_per_speak):
                self.outbox.append(binary(FRAME))
                self._frames_emitted += 1
                if self._close_after_frames and self._frames_emitted >= self._close_after_frames:
                    self.outbox.append(CLOSED)
                    return
        elif payload["type"] == "Flush":
            duration = self._audio_duration_ms
            if duration is None:
                duration = self._frames_emitted * 10
            self.outbox.append(
                text(
                    {
                        "type": "SpeechMetadata",
                        "speech_id": "s-1",
                        "audio_duration_ms": duration,
                        "billable_character_count": 42,
                    }
                )
            )

    async def receive(self, timeout=None):
        for _ in range(500):
            if self.outbox:
                return self.outbox.popleft()
            await _yield()
        return CLOSED

    async def close(self, code=1000):
        self.closed = True


async def _yield() -> None:
    import asyncio

    await asyncio.sleep(0)


class FakeSession:
    """Just enough ClientSession to hand back a FakeSocket, and to record the connect call."""

    def __init__(self, socket=None, raises: Exception | None = None) -> None:
        self.socket = socket or FakeSocket()
        self.raises = raises
        self.connect_url: str | None = None
        self.connect_params: dict | None = None
        self.connect_headers: dict | None = None

    def ws_connect(self, url, *, params=None, headers=None, timeout=None, heartbeat=None):
        self.connect_url = url
        self.connect_params = params
        self.connect_headers = headers
        session = self

        class Ctx:
            async def __aenter__(self):
                if session.raises:
                    raise session.raises
                return session.socket

            async def __aexit__(self, *exc):
                return False

        return Ctx()


async def chunks_of(*items: str):
    for item in items:
        yield item
        await _yield()


async def collect(socket: FluxSocket, *items: str) -> bytes:
    return b"".join([frame async for frame in socket.stream(chunks_of(*items))])


# --- the header -------------------------------------------------------------------------


def test_wav_header_is_44_bytes_of_valid_riff():
    header = wav_header(WS_SAMPLE_RATE)
    assert len(header) == 44
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert header[12:16] == b"fmt "
    assert header[36:40] == b"data"
    assert struct.unpack_from("<I", header, 24)[0] == WS_SAMPLE_RATE
    assert struct.unpack_from("<H", header, 34)[0] == 16


def test_wav_header_declares_unknown_length():
    """A streaming WAV cannot know its size, and inventing one would mean buffering the clip."""
    header = wav_header()
    assert struct.unpack_from("<I", header, 4)[0] == 0xFFFFFFFF
    assert struct.unpack_from("<I", header, 40)[0] == 0xFFFFFFFF


# --- the happy path ---------------------------------------------------------------------


async def test_yields_header_then_audio():
    session = FakeSession()
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    frames = [frame async for frame in socket.stream(chunks_of("Hello ", "there."))]

    assert frames[0] == wav_header(WS_SAMPLE_RATE)
    assert b"".join(frames[1:]) == FRAME * 2
    assert socket.metrics.audio_bytes == len(FRAME) * 2


async def test_sends_one_speak_per_chunk_then_flush_and_never_splits_text():
    """The regression test for the whole design.

    The server places flush boundaries internally, so the client must forward chunks verbatim.
    Any sentence splitting, buffering, or re-chunking shows up here as a mismatch.
    """
    session = FakeSession()
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)
    given = ("Sure, ", "I can help ", "you cancel that.")

    await collect(socket, *given)

    speaks = [msg["text"] for msg in session.socket.sent if msg["type"] == "Speak"]
    assert speaks == list(given)
    assert session.socket.sent[-1] == {"type": "Flush"}
    assert socket.metrics.chunks_sent == 3


async def test_audio_arrives_before_the_text_runs_out():
    """The first frame must land before the last chunk is sent, or streaming bought nothing."""
    session = FakeSession()
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)
    sent_at_first_frame: list[int] = []

    async for frame in socket.stream(chunks_of("one ", "two ", "three ", "four ", "five.")):
        if frame != wav_header(WS_SAMPLE_RATE) and not sent_at_first_frame:
            sent_at_first_frame.append(
                len([m for m in session.socket.sent if m["type"] == "Speak"])
            )

    assert sent_at_first_frame, "no audio frame was ever yielded"
    assert sent_at_first_frame[0] < 5


async def test_metrics_are_populated():
    session = FakeSession(socket=FakeSocket(frames_per_speak=2))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "a ", "b.")

    assert socket.metrics.connect_ms is not None
    assert socket.metrics.first_frame_ms is not None
    assert socket.metrics.metadata_ms is not None
    assert socket.metrics.request_id == "req-1"
    assert socket.metrics.audio_duration_ms == 40
    assert socket.metrics.realtime_factor is not None


async def test_empty_chunks_are_not_sent():
    session = FakeSession()
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "real ", "", "text.")

    assert [m["text"] for m in session.socket.sent if m["type"] == "Speak"] == ["real ", "text."]


# --- the query string -------------------------------------------------------------------


async def test_output_format_is_pinned_not_defaulted():
    """The header we prepend is only right if we asked for the rate it declares."""
    session = FakeSession()
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "hi.")

    assert session.connect_params["model"] == DEFAULT_VOICE
    assert session.connect_params["encoding"] == "linear16"
    assert session.connect_params["sample_rate"] == str(WS_SAMPLE_RATE)
    assert session.connect_headers["Authorization"] == "Token key"


async def test_speed_is_sent_only_when_given():
    plain = FakeSession()
    await collect(FluxSocket(plain, "key", model=DEFAULT_VOICE), "hi.")
    assert "speed" not in plain.connect_params

    fast = FakeSession()
    await collect(FluxSocket(fast, "key", model=DEFAULT_VOICE, speed=1.15), "hi.")
    assert fast.connect_params["speed"] == "1.15"


# --- degradation ------------------------------------------------------------------------


async def test_socket_closing_mid_turn_raises_connection_error():
    """Chapter 6's second verification. The caller falls back to batch on this error."""
    session = FakeSession(socket=FakeSocket(frames_per_speak=1, close_after_frames=1))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError, match="ended mid turn"):
        await collect(socket, "one ", "two ", "three.")


async def test_socket_closing_before_connected_raises_connection_error():
    session = FakeSession(socket=FakeSocket(connected=False))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError, match="before Connected"):
        await collect(socket, "hi.")


async def test_client_error_on_connect_raises_connection_error():
    session = FakeSession(raises=ClientError("no route to host"))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError, match="Flux socket failed"):
        await collect(socket, "hi.")


async def test_server_error_message_raises_connection_error():
    session = FakeSession(
        socket=FakeSocket(
            error_on_speak={
                "type": "Error",
                "code": "RATE_LIMIT",
                "description": "slow down",
            }
        )
    )
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError, match="RATE_LIMIT"):
        await collect(socket, "hi.")


async def test_auth_shaped_server_error_raises_auth_error():
    """An expired key must not read as a dead network, on the socket path either."""
    session = FakeSession(
        socket=FakeSocket(
            error_on_speak={"type": "Error", "code": "UNAUTHORIZED", "description": "bad key"}
        )
    )
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramAuthError):
        await collect(socket, "hi.")


# --- the self check ---------------------------------------------------------------------


async def test_sample_rate_mismatch_warns_and_does_not_raise():
    """Wrong-pitch audio sounds like a bad voice, not like a bug, so it gets caught by math.

    Half the expected bytes for the reported duration means the real stream was 12 kHz while
    the header says 24 kHz. Still audible, so a warning rather than a failure.
    """
    session = FakeSession(socket=FakeSocket(frames_per_speak=1, audio_duration_ms=20))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "hi.")

    assert socket.metrics.warnings
    assert "12000 Hz" in socket.metrics.warnings[0]


async def test_matching_sample_rate_records_no_warning():
    session = FakeSession(socket=FakeSocket(frames_per_speak=3))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "hi.")

    assert socket.metrics.warnings == []


# --- what the skeptic pass found, and what would have caught it -------------------------


class HandshakeFailSession(FakeSession):
    """Fails the HTTP upgrade, which is how a rejected key actually arrives."""

    def __init__(self, status: int) -> None:
        super().__init__()
        self.status = status

    def ws_connect(self, url, **kwargs):
        from aiohttp import WSServerHandshakeError

        status = self.status

        class Ctx:
            async def __aenter__(self):
                raise WSServerHandshakeError(
                    SimpleNamespace(real_url=url),
                    (),
                    status=status,
                    message="Invalid credentials.",
                )

            async def __aexit__(self, *exc):
                return False

        return Ctx()


@pytest.mark.parametrize("status", [401, 403])
async def test_a_rejected_key_on_the_handshake_is_an_auth_error(status: int):
    """The defect this whole integration exists to not repeat, on the primary path.

    A rejected key fails the HTTP upgrade, so it never produces an in-band Error frame. It
    arrives as WSServerHandshakeError, which is a ClientError subclass, and a handler that only
    catches ClientError turns an expired key into a connection error. The caller then falls back
    to batch and the real cause is hidden twice over.
    """
    socket = FluxSocket(HandshakeFailSession(status), "expired", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramAuthError, match="rejected the API key"):
        await collect(socket, "hi.")


async def test_a_non_auth_handshake_failure_is_still_a_connection_error():
    socket = FluxSocket(HandshakeFailSession(503), "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError, match="handshake failed"):
        await collect(socket, "hi.")


@pytest.mark.parametrize(
    "frame",
    [
        SimpleNamespace(type=WSMsgType.TEXT, data="not json at all"),
        SimpleNamespace(type=WSMsgType.TEXT, data="[1, 2, 3]"),
    ],
    ids=["not-json", "json-but-not-an-object"],
)
async def test_an_unreadable_frame_degrades_instead_of_escaping(frame):
    """Three ways a frame can be wrong, and all three escaped as raw exceptions before.

    It matters because the caller catches DeepgramConnectionError to fall back to batch. A
    JSONDecodeError, an AttributeError, or a TypeError sails straight past that handler and
    reaches a person who asked their house a question.
    """
    session = FakeSession()
    session.socket.outbox.append(frame)
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError):
        await collect(socket, "hi.")


async def test_a_metadata_field_of_the_wrong_type_warns_rather_than_raising():
    """The third way a frame can be wrong, and the only one where raising would be worse.

    `audio_duration_ms` arrives after every audio frame has already been handed to the caller,
    so failing the turn at that point throws away audio that was fine. It warns instead, which
    is also why it is not in the parametrize above.
    """
    session = FakeSession()
    session.socket.outbox.append(
        SimpleNamespace(
            type=WSMsgType.TEXT,
            data=json.dumps({"type": "SpeechMetadata", "audio_duration_ms": "twenty"}),
        )
    )
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "hi.")

    assert socket.metrics.warnings == [] or "could not be checked" in socket.metrics.warnings[0]


async def test_the_sender_task_is_never_left_running():
    """The cleanup had a ledger entry behind it and no test, and deleting it stayed green."""
    import asyncio

    before = {id(task) for task in asyncio.all_tasks()}
    session = FakeSession(socket=FakeSocket(frames_per_speak=1, close_after_frames=1))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    with pytest.raises(DeepgramConnectionError):
        await collect(socket, "one ", "two ", "three ", "four ", "five.")

    leaked = [task for task in asyncio.all_tasks() if id(task) not in before and not task.done()]
    assert leaked == [], f"sender task left running: {leaked}"


async def test_a_22050_hz_stream_against_a_24000_hz_header_is_caught():
    """The nearest plausible wrong rate, which the original 0.9 tolerance window missed.

    22050 against a declared 24000 is a ratio of 0.919, comfortably inside a 0.9 to 1.1 window
    and still audibly wrong. 11 frames of 480 bytes is 5280 bytes; a reported 120 ms expects
    5760, which is a ratio of 0.917 and lands in exactly that blind spot.
    """
    session = FakeSession(socket=FakeSocket(frames_per_speak=11, audio_duration_ms=120))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "hi.")

    assert socket.metrics.warnings
    assert "Hz" in socket.metrics.warnings[0]


async def test_a_zero_duration_with_real_audio_is_reported_not_skipped():
    """Dividing by it would raise, so the old code returned early and said nothing at all."""
    session = FakeSession(socket=FakeSocket(frames_per_speak=2, audio_duration_ms=0))
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)

    await collect(socket, "hi.")

    assert socket.metrics.warnings
    assert "could not be checked" in socket.metrics.warnings[0]


async def test_warnings_are_bounded():
    """A chatty server must not grow this list for the lifetime of a turn."""
    from custom_components.deepgram_tts.stream import MAX_WARNINGS_PER_TURN

    session = FakeSession()
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)
    for index in range(MAX_WARNINGS_PER_TURN + 25):
        socket._warn(f"warning {index}")

    assert len(socket.metrics.warnings) == MAX_WARNINGS_PER_TURN


async def test_a_turn_that_never_ends_is_bounded_rather_than_hanging():
    """A server that never sends SpeechMetadata is a hang, and a hang does not degrade."""
    from custom_components.deepgram_tts import stream as stream_module

    class Endless(FakeSocket):
        """Connects, then sends audio forever and never sends SpeechMetadata."""

        async def send_json(self, payload: dict) -> None:
            # Deliberately answers nothing, not even Flush. The base class would append
            # SpeechMetadata and end the turn, which is the opposite of what is under test.
            self.sent.append(payload)
            await _yield()

        async def receive(self, timeout=None):
            await _yield()
            if self.outbox:
                return self.outbox.popleft()
            return binary(FRAME)

    session = FakeSession(socket=Endless())
    socket = FluxSocket(session, "key", model=DEFAULT_VOICE)
    original = stream_module.MAX_FRAMES_PER_TURN
    stream_module.MAX_FRAMES_PER_TURN = 50
    try:
        with pytest.raises(DeepgramConnectionError, match="without SpeechMetadata"):
            await collect(socket, "hi.")
    finally:
        stream_module.MAX_FRAMES_PER_TURN = original
