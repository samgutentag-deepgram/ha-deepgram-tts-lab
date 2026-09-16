"""Text to speech support for Deepgram.

Chapter 5 of the build: the batch path. `async_get_tts_audio` resolves a voice out of the
merged catalog and posts once to `/v2/speak` for Flux or `/v1/speak` for Aura.

`async_stream_tts_audio` is deliberately absent. Home Assistant detects streaming support by
comparing `self.__class__.async_stream_tts_audio` against the base method, so defining it here
at all, even as a stub that raises, would route every Assist pipeline response down a websocket
path that does not exist yet, while direct `tts.speak` calls kept working and hid the breakage.
That is exactly how the integration this project replaces shipped broken. Chapter 6 adds the
method and the socket client behind it in the same commit, on its own branch.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
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
)
from .errors import DeepgramError
from .models import VoiceCatalog, family_for_model

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
