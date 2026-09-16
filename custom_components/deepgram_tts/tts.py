"""Text to speech support for Deepgram.

Two paths. `async_get_tts_audio` posts once and returns a whole clip. `async_stream_tts_audio`
opens the Flux websocket, forwards each chunk of the message as it arrives, and yields audio
frames while the text is still coming in.

**Defining `async_stream_tts_audio` is itself the opt-in.** Home Assistant detects streaming
support by comparing `self.__class__.async_stream_tts_audio` against the base method, so the
moment this method exists every Assist pipeline response routes down it, while direct
`tts.speak` calls keep using the batch path and hide any breakage. That is exactly how the
integration this project replaces shipped broken, and it is why this method landed on its own
branch after the batch path was proven on real hardware rather than alongside it.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
import logging
from typing import Any

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DeepgramClient
from .catalog import resolve_voice, supported_languages, voices_for_language
from .const import (
    CONF_SPEED,
    CONF_VOICE,
    DEFAULT_LANGUAGE,
    DEFAULT_VOICE,
    DEVICE_MODEL_AURA,
    DEVICE_MODEL_FLUX,
    DOMAIN,
    FAMILY_FLUX,
    MANUFACTURER,
    PREFERRED_FORMAT_PARAMS,
    STREAM_CONTAINER,
    STREAM_ENCODING,
    STREAM_EXTENSION,
)
from .errors import DeepgramConnectionError, DeepgramError
from .models import VoiceCatalog, VoiceInfo, family_for_model

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Deepgram TTS entity for one config entry."""
    runtime = entry.runtime_data
    client = DeepgramClient(async_get_clientsession(hass), runtime.api_key)
    # The catalog is handed in, never fished out of the client. Reaching through private
    # attributes for it was a real defect in the codebase this project replaces.
    async_add_entities([DeepgramTTSEntity(entry, client, runtime.catalog)])


def _configured_voice(entry) -> str:
    """Return the voice this entry was set up with.

    Options win over data, because the options flow is where a voice gets changed after setup.
    """
    return entry.options.get(CONF_VOICE) or entry.data.get(CONF_VOICE) or DEFAULT_VOICE


def _format_params(preferred_format: str | None) -> tuple[str | None, str | None]:
    """Translate Home Assistant's preferred_format into a Deepgram encoding and container."""
    if not preferred_format:
        return None, None

    params = PREFERRED_FORMAT_PARAMS.get(preferred_format.lower())
    if params is None:
        _LOGGER.debug(
            "No Deepgram encoding for preferred_format=%s; letting Home Assistant convert",
            preferred_format,
        )
        return None, None

    return params


class DeepgramTTSEntity(TextToSpeechEntity):
    """A Deepgram voice exposed to Home Assistant as a TTS entity."""

    def __init__(self, entry, client: DeepgramClient, catalog: VoiceCatalog) -> None:
        """Bind the entity to its config entry, API client, and voice catalog."""
        self._entry = entry
        self._client = client
        self._catalog = catalog
        self._voice_id = _configured_voice(entry)
        self._speed: float | None = entry.options.get(CONF_SPEED)

        is_flux = family_for_model(self._voice_id) == FAMILY_FLUX
        self._attr_unique_id = entry.entry_id
        # The entry title names the chosen voice, so two entries produce distinguishable entity
        # ids: tts.deepgram_flux_haley next to tts.deepgram_aura_celeste. Deliberately not
        # `_attr_has_entity_name` with a null name: that leaves `entity.name` None, and the tts
        # manager refuses to synthesize with "TTS engine name is not set." Same shape as core's
        # google_cloud entity.
        self._attr_name = entry.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL_FLUX if is_flux else DEVICE_MODEL_AURA,
            entry_type=DeviceEntryType.SERVICE,
        )

        self._attr_default_language = DEFAULT_LANGUAGE
        # Base codes only. Deepgram reports en and en-US on the same voice, and handing Home
        # Assistant both makes one language look like two. DEFAULT_LANGUAGE is unioned in so
        # default_language is always a member: an empty catalog should fail with a Deepgram
        # error naming the cause, not with HA's "Language 'en' not supported".
        self._attr_supported_languages = sorted({DEFAULT_LANGUAGE, *supported_languages(catalog)})
        self._attr_supported_options = [ATTR_VOICE, ATTR_PREFERRED_FORMAT, CONF_SPEED]

        default_options: dict[str, Any] = {ATTR_VOICE: self._voice_id}
        if self._speed is not None:
            default_options[CONF_SPEED] = self._speed
        self._attr_default_options = default_options

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return the voices that can speak `language`, Flux first.

        None rather than an empty list for a language nobody in the catalog speaks, because an
        empty list reads to Home Assistant as a restriction to nothing.
        """
        voices = [
            Voice(voice.voice_id, voice.name)
            for voice in voices_for_language(self._catalog, language)
        ]
        return voices or None

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize `message` and return the audio Deepgram produced.

        Typed errors from the client propagate untouched. A broad handler here would rewrap an
        expired key as a generic failure and leave the caller unable to tell it from a dead
        network, which is the defect this whole integration exists to avoid.
        """
        options = options or {}
        preferred = options.get(ATTR_VOICE) or self._voice_id

        # resolve_voice is the only gate on settled decision 4. It drops a preferred voice that
        # cannot speak `language`, which is what keeps a Spanish pipeline off every Flux voice.
        voice = resolve_voice(self._catalog, language, preferred)
        if voice is None:
            raise DeepgramError(f"No Deepgram voice in the merged catalog can speak {language!r}")

        encoding, container = _format_params(options.get(ATTR_PREFERRED_FORMAT))
        # Aura has no speed parameter at all, so sending one is meaningless even though the
        # client would drop it anyway.
        speed = options.get(CONF_SPEED) if voice.is_flux else None

        # Logged because the model actually sent is the only thing worth checking on a real
        # instance. The configured option, the requested language and the resolved voice can all
        # disagree, and a hand-check that reads the option learns nothing.
        _LOGGER.debug(
            "Synthesizing %d chars as %s (%s) for language %s, speed=%s, format=%s",
            len(message),
            voice.voice_id,
            voice.family,
            language,
            speed,
            options.get(ATTR_PREFERRED_FORMAT) or "default",
        )

        result = await self._client.async_synthesize(
            message,
            model=voice.voice_id,
            encoding=encoding,
            container=container,
            speed=speed,
        )

        # Straight through, no decode and no re-encode. Home Assistant converts in
        # _async_convert_audio when the requested format differs from what came back, and a
        # transcode per spoken sentence on a Raspberry Pi buys nothing.
        return result.extension, result.audio

    async def async_stream_tts_audio(self, request: TTSAudioRequest) -> TTSAudioResponse:
        """Stream audio while the message is still arriving.

        The extension has to be declared before the first byte is fetched, and the socket may
        fail at any point, so both the socket and the batch fallback produce WAV. Nothing has
        to be reconciled later and Home Assistant converts once if the pipeline wanted
        something else.

        WAV is also the format the playback devices want. An ESPHome voice satellite with the
        speaker flag hard-refuses anything else with "Only WAV audio can be streamed", so this
        is not only the easiest container to emit from raw frames.
        """
        options = request.options or {}
        preferred = options.get(ATTR_VOICE) or self._voice_id
        voice = resolve_voice(self._catalog, request.language, preferred)
        if voice is None:
            raise DeepgramError(
                f"No Deepgram voice in the merged catalog can speak {request.language!r}"
            )

        speed = options.get(CONF_SPEED) if voice.is_flux else None

        if not voice.is_flux:
            # Aura has no socket at all. Settled decision 5: fall back to batch rather than
            # refuse, so a Spanish pipeline still speaks.
            _LOGGER.debug(
                "%s is not a Flux voice, streaming turn served from batch", voice.voice_id
            )
            data_gen = self._batch_stream(voice, request.message_gen, speed, reason=None)
        else:
            data_gen = self._socket_stream(voice, request.message_gen, speed)

        return TTSAudioResponse(extension=STREAM_EXTENSION, data_gen=data_gen)

    async def _socket_stream(
        self, voice: VoiceInfo, message_gen: AsyncIterator[str], speed: float | None
    ) -> AsyncGenerator[bytes]:
        """Yield the turn off the Flux socket, degrading to batch rather than raising.

        Two failure windows, and they need different answers. Before any audio has reached the
        caller, the whole turn can still be served from the batch endpoint and nobody hears a
        difference. Once audio has gone out, a batch clip would arrive with its own WAV header
        behind the one already sent, so the turn ends where it ends and the log says why.
        """
        consumed: list[str] = []
        socket = self._client.stream(model=voice.voice_id, speed=speed)

        header: bytes | None = None
        audio_started = False

        try:
            async for frame in socket.stream(_tee(message_gen, consumed)):
                # The socket yields its WAV header before the first audio frame, and a header
                # already sent is what makes a clean fallback impossible. Hold it until audio
                # actually exists. It costs 44 bytes of delay and buys the fallback window.
                if not audio_started and socket.metrics.first_frame_ms is None:
                    header = frame
                    continue
                if not audio_started:
                    audio_started = True
                    if header is not None:
                        yield header
                        header = None
                yield frame
        except DeepgramConnectionError as err:
            if audio_started:
                _LOGGER.warning(
                    "Flux socket dropped after %d bytes of audio, ending the turn early: %s",
                    socket.metrics.audio_bytes,
                    err,
                )
                return
            _LOGGER.warning("Flux socket failed before any audio, serving from batch: %s", err)
            fallback = self._batch_stream(
                voice, message_gen, speed, reason=str(err), consumed=consumed
            )
            async for frame in fallback:
                yield frame
            return

        if socket.metrics.first_frame_ms is not None:
            _LOGGER.debug(
                "Flux socket turn: first frame %.0f ms, complete %.0f ms, %d bytes, %d chunks",
                socket.metrics.first_frame_ms,
                socket.metrics.metadata_ms or 0,
                socket.metrics.audio_bytes,
                socket.metrics.chunks_sent,
            )

    async def _batch_stream(
        self,
        voice: VoiceInfo,
        message_gen: AsyncIterator[str],
        speed: float | None,
        *,
        reason: str | None,
        consumed: list[str] | None = None,
    ) -> AsyncGenerator[bytes]:
        """Serve a streaming request from the batch endpoint as one WAV.

        `consumed` holds whatever the socket already pulled off `message_gen` before it failed.
        Draining the rest of a generator whose consumer was cancelled mid-iteration can leave it
        in a state that raises, so a failure to drain costs the tail of the sentence rather than
        the whole turn.
        """
        parts: list[str] = list(consumed or [])
        try:
            async for chunk in message_gen:
                parts.append(chunk)
        except (RuntimeError, StopAsyncIteration) as err:
            _LOGGER.warning(
                "Could not read the rest of the message after a socket failure, "
                "speaking the %d chunks already received: %s",
                len(parts),
                err,
            )

        text = "".join(parts)
        if not text:
            _LOGGER.warning("Nothing left to synthesize for this turn (reason: %s)", reason)
            return

        result = await self._client.async_synthesize(
            text,
            model=voice.voice_id,
            encoding=STREAM_ENCODING,
            container=STREAM_CONTAINER,
            speed=speed,
        )
        yield result.audio


async def _tee(source: AsyncIterator[str], sink: list[str]) -> AsyncGenerator[str]:
    """Forward each chunk immediately while keeping a copy for a possible batch fallback.

    This is not the buffering HANDOFF section 2.2 warns about. Nothing waits: each chunk is
    yielded the moment it arrives. The copy exists only because `message_gen` is single use, so
    a fallback that has to re-synthesize the turn has no other way to know what the text was.
    """
    async for chunk in source:
        sink.append(chunk)
        yield chunk
