"""The streaming path, through the tts manager the way Home Assistant itself drives it.

The socket is faked at `ClientSession.ws_connect`, so the real `FluxSocket` runs and the real
`DeepgramTTSEntity` consumes it. Only the network is replaced.

Two of these tests are worth more than the rest. One puts the streaming WAV through Home
Assistant's own ffmpeg conversion, which is the first check anywhere that the unknown-length
RIFF header this integration emits is actually readable. The other kills the socket and asserts
the turn still speaks, which is chapter 6's second verification from HANDOFF section 6.1.
"""

from collections import deque
import json
import struct
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientError, WSMsgType
from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    async_get_media_source_audio,
    generate_media_source_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.const import (
    CONF_VOICE,
    DEFAULT_VOICE,
    DOMAIN,
    URL_MODELS_AURA,
    URL_MODELS_FLUX,
    URL_SPEAK_AURA,
    URL_SPEAK_FLUX,
    WS_SAMPLE_RATE,
)
from custom_components.deepgram_tts.stream import wav_header

AURA_ES_VOICE = "aura-2-celeste-es"

# 20 ms of real 24 kHz mono linear16. Actual samples, not filler, because these bytes go
# through ffmpeg in one of the tests below and a fake frame would fail for the wrong reason.
FRAME = struct.pack("<480h", *[(i * 97 % 2000) - 1000 for i in range(480)])

# What the batch fallback serves. A whole small WAV, since the fallback yields one blob.
FALLBACK_WAV = wav_header(WS_SAMPLE_RATE) + FRAME * 10


def text_frame(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(payload))


def binary_frame(data: bytes) -> SimpleNamespace:
    return SimpleNamespace(type=WSMsgType.BINARY, data=data)


CLOSED = SimpleNamespace(type=WSMsgType.CLOSED, data=None)


class FakeSocket:
    """Answers Speak with audio and Flush with SpeechMetadata, like the real endpoint.

    A state machine rather than a fixed script, so a client that sent everything before reading
    anything would still be visible as such.
    """

    def __init__(self, *, frames_per_speak: int = 2, fail_after_frames: int | None = None) -> None:
        self.sent: list[dict] = []
        self.outbox: deque = deque([text_frame({"type": "Connected", "request_id": "req-1"})])
        self._frames_per_speak = frames_per_speak
        self._fail_after_frames = fail_after_frames
        self._emitted = 0
        self._started = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)
        await _yield()

        if payload["type"] == "Speak":
            if not self._started:
                self.outbox.append(text_frame({"type": "SpeechStarted", "speech_id": "s-1"}))
                self._started = True
            for _ in range(self._frames_per_speak):
                self.outbox.append(binary_frame(FRAME))
                self._emitted += 1
                if self._fail_after_frames is not None and self._emitted >= self._fail_after_frames:
                    self.outbox.append(CLOSED)
                    return
        elif payload["type"] == "Flush":
            self.outbox.append(
                text_frame(
                    {
                        "type": "SpeechMetadata",
                        "speech_id": "s-1",
                        "audio_duration_ms": self._emitted * 20,
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
        return None


class FailingSocket(FakeSocket):
    """Refuses the connection outright, which is the pre-first-frame fallback window."""


async def _yield() -> None:
    import asyncio

    await asyncio.sleep(0)


def patch_ws(hass: HomeAssistant, socket: FakeSocket | None, *, raises: Exception | None = None):
    """Replace ws_connect on the session hass hands the integration."""
    session = async_get_clientsession(hass)

    def ws_connect(url, **kwargs):
        class Ctx:
            async def __aenter__(self):
                if raises is not None:
                    raise raises
                return socket

            async def __aexit__(self, *exc):
                return False

        ws_connect.calls.append((url, kwargs))
        return Ctx()

    ws_connect.calls = []
    return patch.object(session, "ws_connect", ws_connect), ws_connect


@pytest.fixture
def mock_api(
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """Both catalogs, plus a batch endpoint that serves a real WAV for the fallback."""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(URL_MODELS_AURA, json=multilingual_aura_payload)
    aioclient_mock.post(URL_SPEAK_FLUX, content=FALLBACK_WAV, headers={"Content-Type": "audio/wav"})
    aioclient_mock.post(URL_SPEAK_AURA, content=FALLBACK_WAV, headers={"Content-Type": "audio/wav"})


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = hass.states.async_entity_ids("tts")
    assert len(ids) == 1
    return ids[0]


async def stream_through_hass(
    hass: HomeAssistant,
    entity_id: str,
    message: str,
    *,
    language: str | None = None,
    options: dict | None = None,
) -> tuple[str, bytes]:
    """Drive the tts manager, which prefers the streaming path whenever it exists.

    cache=False on every call: the manager keys its memory cache on message, language, options,
    and engine, so a repeated message replays the first result and never reaches the entity.
    """
    return await async_get_media_source_audio(
        hass,
        generate_media_source_id(
            hass,
            message=message,
            engine=entity_id,
            language=language,
            options=options,
            cache=False,
        ),
    )


def flux_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Flux (Haley)",
        data={"api_key": "test-key"},
        options={CONF_VOICE: DEFAULT_VOICE},
    )


def aura_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Aura (Celeste)",
        data={"api_key": "test-key"},
        options={CONF_VOICE: AURA_ES_VOICE},
    )


# --- the happy path ---------------------------------------------------------------------


async def test_a_flux_turn_comes_off_the_socket_as_wav(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    entity_id = await setup_entry(hass, flux_entry())
    socket = FakeSocket(frames_per_speak=2)
    patcher, ws = patch_ws(hass, socket)

    with patcher:
        extension, audio = await stream_through_hass(
            hass, entity_id, "The back door is unlocked.", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    assert extension == "wav"
    assert audio.startswith(b"RIFF")
    assert audio[8:12] == b"WAVE"
    # Header once, not once per frame.
    assert audio.count(b"RIFF") == 1
    assert len(audio) > 44
    # And no batch request was needed.
    assert not [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert len(ws.calls) == 1


async def test_the_socket_is_asked_for_the_rate_the_header_declares(
    hass: HomeAssistant, mock_api: None
) -> None:
    """The WAV header is an assertion, so the request has to pin the same format."""
    entity_id = await setup_entry(hass, flux_entry())
    patcher, ws = patch_ws(hass, FakeSocket())

    with patcher:
        await stream_through_hass(
            hass, entity_id, "Pin the format.", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    params = ws.calls[0][1]["params"]
    assert params["model"] == DEFAULT_VOICE
    assert params["encoding"] == "linear16"
    assert params["sample_rate"] == str(WS_SAMPLE_RATE)


async def test_every_chunk_is_forwarded_verbatim_and_nothing_is_resegmented(
    hass: HomeAssistant, mock_api: None
) -> None:
    """The server places the flush boundaries, so the client must not place any of its own."""
    entity_id = await setup_entry(hass, flux_entry())
    socket = FakeSocket()
    patcher, _ = patch_ws(hass, socket)

    # The manager hands the entity one chunk per message, so this asserts the shape rather than
    # a token stream: one Speak, then Flush, and no splitting on punctuation.
    message = "Sure. I can help. Two sentences, one Speak."
    with patcher:
        await stream_through_hass(hass, entity_id, message, options={ATTR_PREFERRED_FORMAT: "wav"})

    speaks = [msg["text"] for msg in socket.sent if msg["type"] == "Speak"]
    assert speaks == [message]
    assert socket.sent[-1] == {"type": "Flush"}


async def test_the_streaming_wav_survives_home_assistants_own_ffmpeg_pass(
    hass: HomeAssistant, mock_api: None
) -> None:
    """The first real check on the unknown-length RIFF header.

    The header declares 0xFFFFFFFF for both size fields, because a stream cannot know its own
    length and inventing one would mean buffering the clip. Nothing had confirmed that anything
    downstream accepts it. Asking the manager for mp3 while the entity produces wav forces
    `_async_convert_audio`, which shells out to real ffmpeg on this machine, so a header ffmpeg
    rejects fails this test.
    """
    entity_id = await setup_entry(hass, flux_entry())
    patcher, _ = patch_ws(hass, FakeSocket(frames_per_speak=8))

    with patcher:
        extension, audio = await stream_through_hass(hass, entity_id, "Convert me to mp3.")

    assert extension == "mp3"
    assert audio, "ffmpeg produced no output from the streaming WAV"
    assert not audio.startswith(b"RIFF")


# --- degradation ------------------------------------------------------------------------


async def test_a_socket_that_never_connects_degrades_to_batch(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """Chapter 6's second verification, the pre-first-frame window.

    Nothing has reached the caller yet, so the whole turn can still be served from the batch
    endpoint and a listener hears no difference.
    """
    entity_id = await setup_entry(hass, flux_entry())
    patcher, _ = patch_ws(hass, None, raises=ClientError("no route to host"))

    with patcher:
        extension, audio = await stream_through_hass(
            hass, entity_id, "Degrade cleanly.", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    assert extension == "wav"
    assert audio == FALLBACK_WAV
    posts = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert len(posts) == 1
    assert posts[0][1].query["model"] == DEFAULT_VOICE
    # The fallback has to request the same container it already promised.
    assert posts[0][1].query["encoding"] == "linear16"
    assert posts[0][1].query["container"] == "wav"


async def test_the_fallback_speaks_the_whole_message_not_a_fragment(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """The text copy exists so a fallback knows what to say. Assert it said all of it."""
    entity_id = await setup_entry(hass, flux_entry())
    patcher, _ = patch_ws(hass, None, raises=ClientError("socket refused"))
    message = "The garage light is still on and the back door is unlocked."

    with patcher:
        await stream_through_hass(hass, entity_id, message, options={ATTR_PREFERRED_FORMAT: "wav"})

    # aioclient_mock records a json= body as the dict itself, not as serialized bytes.
    posts = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert posts[0][2]["text"] == message


async def test_a_socket_that_drops_mid_turn_ends_early_instead_of_raising(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """The post-first-frame window, where a batch clip cannot be appended.

    Audio has already gone out with a WAV header in front of it, so serving the batch clip now
    would put a second header in the middle of the stream. The turn ends where it ends. What
    must not happen is an exception reaching a person who asked their house a question.
    """
    entity_id = await setup_entry(hass, flux_entry())
    patcher, _ = patch_ws(hass, FakeSocket(frames_per_speak=1, fail_after_frames=1))

    with patcher:
        extension, audio = await stream_through_hass(
            hass, entity_id, "Cut me off.", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    assert extension == "wav"
    assert audio.startswith(b"RIFF")
    assert audio.count(b"RIFF") == 1
    # Truncated, not empty, and not doubled by a fallback.
    assert 44 < len(audio) < len(FALLBACK_WAV)
    assert not [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]


async def test_an_aura_voice_never_opens_a_socket(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """There is no Aura websocket. Settled decision 5: serve it from batch, do not refuse."""
    entity_id = await setup_entry(hass, aura_entry())
    patcher, ws = patch_ws(hass, FakeSocket())

    with patcher:
        extension, audio = await stream_through_hass(
            hass, entity_id, "Hola.", language="es", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    assert extension == "wav"
    assert audio == FALLBACK_WAV
    assert ws.calls == []
    posts = [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
    assert posts[0][1].query["model"] == AURA_ES_VOICE
    assert str(posts[0][1]).startswith(URL_SPEAK_AURA)


async def test_a_spanish_pipeline_still_cannot_reach_flux_when_streaming(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """Settled decision 4 holds on the streaming path too, not only the batch one."""
    entity_id = await setup_entry(hass, flux_entry())
    patcher, ws = patch_ws(hass, FakeSocket())

    with patcher:
        await stream_through_hass(
            hass, entity_id, "Hola.", language="es", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    assert ws.calls == []
    post = next(call for call in aioclient_mock.mock_calls if call[0].upper() == "POST")
    model = post[1].query["model"]
    assert model.startswith("aura")
    assert not model.startswith("flux")


# --- the real service -------------------------------------------------------------------


async def test_tts_speak_service_round_trip(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """The real service end to end, now down the socket: tts.speak, then fetch the stream.

    tts.speak itself synthesizes nothing. It hands the player a media-source URL and returns,
    and audio is produced only when something fetches that stream. On real hardware a silent
    speaker after a clean service call is a playback problem, not a synthesis one.
    """
    entity_id = await setup_entry(hass, flux_entry())
    played = async_mock_service(hass, "media_player", "play_media")
    patcher, ws = patch_ws(hass, FakeSocket(frames_per_speak=8))

    with patcher:
        await hass.services.async_call(
            "tts",
            "speak",
            {
                "entity_id": entity_id,
                "media_player_entity_id": "media_player.kitchen",
                "message": "Your appointment is confirmed for 3pm tomorrow.",
                "cache": False,
            },
            blocking=True,
        )

        assert len(played) == 1
        extension, audio = await async_get_media_source_audio(
            hass, played[0].data["media_content_id"]
        )

    assert extension == "mp3"
    assert audio
    assert len(ws.calls) == 1


async def test_an_expired_key_surfaces_as_auth_and_does_not_fall_back(
    hass: HomeAssistant, mock_api: None, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected key must not degrade quietly. It is the one failure batch cannot rescue.

    Falling back here would send the same dead key to `/v2/speak`, fail again, and report
    whichever error came second. The point of typed errors is that a caller can tell an expired
    key from a flaky network, so this one propagates.
    """
    from aiohttp import WSServerHandshakeError

    entity_id = await setup_entry(hass, flux_entry())
    handshake_401 = WSServerHandshakeError(
        SimpleNamespace(real_url="wss://api.deepgram.com/v2/speak"),
        (),
        status=401,
        message="Invalid credentials.",
    )
    patcher, _ = patch_ws(hass, None, raises=handshake_401)

    with patcher, pytest.raises(HomeAssistantError, match="rejected the API key"):
        await stream_through_hass(
            hass, entity_id, "Expired.", options={ATTR_PREFERRED_FORMAT: "wav"}
        )

    # And it did not quietly try the same dead key against the batch endpoint.
    assert not [call for call in aioclient_mock.mock_calls if call[0].upper() == "POST"]
