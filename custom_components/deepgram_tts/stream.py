"""The Flux TTS websocket client.

Chapter 6's engine, kept out of `tts.py` so the entity stays readable and so this can be tested
without a Home Assistant instance around it.

The shape, from HANDOFF section 3.5: open the socket, send one `Speak` per chunk of text as the
chunk arrives, send `Flush` when the text runs out, and yield binary frames until
`SpeechMetadata`. **The server places flush boundaries internally.** There is no sentence
splitting here, no buffering of the message, and no stitching of fragments, which is why this
file is short. The integration this project replaces spent 206 lines doing that work by hand.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
import json
import logging
import struct
import time
from typing import Any

from aiohttp import ClientError, ClientSession, WSMsgType

from .const import (
    TIMEOUT_WS_CONNECT,
    TIMEOUT_WS_FRAME,
    URL_SPEAK_FLUX_WS,
    WS_BITS_PER_SAMPLE,
    WS_CHANNELS,
    WS_ENCODING,
    WS_SAMPLE_RATE,
)
from .errors import DeepgramAuthError, DeepgramConnectionError

_LOGGER = logging.getLogger(__name__)

# A streaming WAV cannot know its own length up front, so the two size fields carry the
# all-ones sentinel. ffmpeg, which is what Home Assistant converts with, reads to end of stream
# when it sees this. A real length would mean buffering the whole clip, which is the one thing
# streaming exists to avoid.
_UNKNOWN_LENGTH = 0xFFFFFFFF


def wav_header(
    sample_rate: int = WS_SAMPLE_RATE,
    channels: int = WS_CHANNELS,
    bits_per_sample: int = WS_BITS_PER_SAMPLE,
) -> bytes:
    """Build a 44 byte RIFF header for a stream of unknown length."""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        _UNKNOWN_LENGTH,
        b"WAVE",
        b"fmt ",
        16,  # PCM fmt chunk size
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        _UNKNOWN_LENGTH,
    )


@dataclass(slots=True)
class StreamMetrics:
    """What one streamed turn cost, in wall time and bytes.

    Kept because the whole argument for streaming is a claim about time, and a claim about time
    that nothing measures is marketing. `first_frame_ms` is the number that matters.
    """

    connect_ms: float | None = None
    first_frame_ms: float | None = None
    metadata_ms: float | None = None
    audio_bytes: int = 0
    audio_duration_ms: float | None = None
    request_id: str | None = None
    chunks_sent: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def realtime_factor(self) -> float | None:
        """Audio produced per unit of wall time. Above 1.0 means playback cannot starve."""
        if self.audio_duration_ms and self.metadata_ms:
            return self.audio_duration_ms / self.metadata_ms
        return None


class FluxSocket:
    """One turn of speech over `wss://api.deepgram.com/v2/speak`.

    Single use. A new turn gets a new instance, because the metrics belong to the turn.
    """

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        *,
        model: str,
        speed: float | None = None,
        sample_rate: int = WS_SAMPLE_RATE,
    ) -> None:
        """Bind the socket to one model and one output rate."""
        self._session = session
        self._api_key = api_key
        self._model = model
        self._speed = speed
        self._sample_rate = sample_rate
        self.metrics = StreamMetrics()

    @property
    def url(self) -> str:
        """The socket URL, with the output format pinned rather than left to the default."""
        return URL_SPEAK_FLUX_WS

    def _params(self) -> dict[str, str]:
        params = {
            "model": self._model,
            "encoding": WS_ENCODING,
            "sample_rate": str(self._sample_rate),
        }
        if self._speed is not None:
            params["speed"] = str(self._speed)
        return params

    async def stream(self, chunks: AsyncIterator[str]) -> AsyncGenerator[bytes]:
        """Yield a WAV header then the turn's audio frames as they arrive.

        Raise DeepgramConnectionError on any socket failure, so the caller can fall back to the
        batch endpoint. A dropped connection has to degrade, not surface as an error to a user
        who asked their house a question.
        """
        started = time.perf_counter()

        try:
            async with self._session.ws_connect(
                self.url,
                params=self._params(),
                headers={"Authorization": f"Token {self._api_key}"},
                timeout=TIMEOUT_WS_CONNECT,
                heartbeat=None,
            ) as socket:
                await self._await_connected(socket, started)

                first_speak = time.perf_counter()
                yield wav_header(self._sample_rate)

                # The sender runs concurrently with the receive loop on purpose. Sending every
                # chunk before reading anything would serialize the turn and delete the only
                # property that makes streaming worth doing.
                sender = asyncio.create_task(self._send(socket, chunks))
                try:
                    async for frame in self._receive(socket, first_speak):
                        yield frame
                finally:
                    await self._finish_sender(sender)

        except DeepgramAuthError, DeepgramConnectionError:
            raise
        except (ClientError, TimeoutError, OSError) as err:
            raise DeepgramConnectionError(f"Flux socket failed: {err}") from err

        self._check_sample_rate()

    async def _await_connected(self, socket: Any, started: float) -> None:
        """Block until the server says Connected, so a slow handshake is timed separately."""
        while True:
            message = await socket.receive(timeout=TIMEOUT_WS_CONNECT)

            if message.type is WSMsgType.TEXT:
                event = json.loads(message.data)
                if event.get("type") == "Connected":
                    self.metrics.connect_ms = (time.perf_counter() - started) * 1000
                    self.metrics.request_id = event.get("request_id")
                    return
                if event.get("type") == "Error":
                    raise self._error_from(event)
                continue

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.ERROR):
                raise DeepgramConnectionError(
                    f"Flux socket closed before Connected ({message.type.name})"
                )

    async def _send(self, socket: Any, chunks: AsyncIterator[str]) -> None:
        """Forward each chunk the moment it arrives, then flush.

        No sentence splitting and no buffering. The server decides where the boundaries go, and
        a regex over the text here would undo that.
        """
        async for chunk in chunks:
            if not chunk:
                continue
            await socket.send_json({"type": "Speak", "text": chunk})
            self.metrics.chunks_sent += 1
        await socket.send_json({"type": "Flush"})

    async def _receive(self, socket: Any, first_speak: float) -> AsyncGenerator[bytes]:
        """Yield binary frames until SpeechMetadata says the turn is complete."""
        while True:
            message = await socket.receive(timeout=TIMEOUT_WS_FRAME)

            if message.type is WSMsgType.BINARY:
                if self.metrics.first_frame_ms is None:
                    self.metrics.first_frame_ms = (time.perf_counter() - first_speak) * 1000
                self.metrics.audio_bytes += len(message.data)
                yield message.data
                continue

            if message.type is WSMsgType.TEXT:
                event = json.loads(message.data)
                kind = event.get("type")

                if kind == "SpeechMetadata":
                    # Every frame for the turn arrives between SpeechStarted and this.
                    self.metrics.metadata_ms = (time.perf_counter() - first_speak) * 1000
                    self.metrics.audio_duration_ms = event.get("audio_duration_ms")
                    return
                if kind == "Error":
                    raise self._error_from(event)
                if kind == "Warning":
                    warning = f"{event.get('code')}: {event.get('description')}"
                    self.metrics.warnings.append(warning)
                    _LOGGER.warning("Flux socket warning, %s", warning)
                continue

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.ERROR):
                raise DeepgramConnectionError(
                    f"Flux socket ended mid turn after {self.metrics.audio_bytes} bytes "
                    f"({message.type.name})"
                )

    async def _finish_sender(self, sender: Any) -> None:
        """Stop the sender and surface its failure rather than losing it.

        A cancelled task that swallowed an exception is how a broken send looks like a broken
        receive, and that costs an afternoon to diagnose.
        """
        if not sender.done():
            sender.cancel()
        try:
            await sender
        except asyncio.CancelledError:
            # Ours if the task itself is cancelled. If it is not, the cancellation came from
            # outside and swallowing it here would make this coroutine uncancellable.
            if not sender.cancelled():
                raise
        except (TimeoutError, ClientError, OSError) as err:
            raise DeepgramConnectionError(f"Flux socket send failed: {err}") from err
        except Exception:
            _LOGGER.debug("Flux socket sender ended without completing", exc_info=True)

    def _check_sample_rate(self) -> None:
        """Compare the bytes received against the duration the server reported.

        The socket sends raw frames with no container, so the WAV header's sample rate is an
        assertion we make and not a fact we were told. If it is wrong the audio plays at the
        wrong pitch, which sounds like a bad voice rather than like a bug, so it is worth one
        division to catch. Deliberately a warning: wrong-pitch audio still beats silence.
        """
        if not self.metrics.audio_duration_ms or not self.metrics.audio_bytes:
            return

        bytes_per_ms = self._sample_rate * WS_CHANNELS * WS_BITS_PER_SAMPLE / 8 / 1000
        expected = self.metrics.audio_duration_ms * bytes_per_ms
        if expected <= 0:
            return

        ratio = self.metrics.audio_bytes / expected
        if not 0.9 <= ratio <= 1.1:
            implied = round(self._sample_rate * ratio)
            warning = (
                f"Received {self.metrics.audio_bytes} bytes for "
                f"{self.metrics.audio_duration_ms} ms of audio, which implies about {implied} Hz "
                f"and not the {self._sample_rate} Hz in the WAV header. Playback pitch will be "
                f"wrong by roughly {ratio:.2f}x"
            )
            self.metrics.warnings.append(warning)
            _LOGGER.warning(warning)

    def _error_from(self, event: dict[str, Any]) -> DeepgramConnectionError | DeepgramAuthError:
        """Turn a server Error message into the right typed exception."""
        code = str(event.get("code", ""))
        description = event.get("description", "no description")
        if "AUTH" in code.upper() or "UNAUTHORIZED" in code.upper():
            return DeepgramAuthError(f"Flux socket rejected the API key ({code}): {description}")
        return DeepgramConnectionError(f"Flux socket error {code}: {description}")
