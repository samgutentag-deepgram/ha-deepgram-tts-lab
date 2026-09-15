"""Text to speech support for Deepgram.

Chapter 1 placeholder. The batch path lands in chapter 5 and the websocket in chapter 6; this
exists so the config entry has something to forward to and hassfest sees a real platform.
"""

from __future__ import annotations

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_LANGUAGE, DEFAULT_VOICE, DOMAIN
from .errors import DeepgramRequestError


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Deepgram TTS entity."""
    async_add_entities([DeepgramTTSEntity(entry)])


class DeepgramTTSEntity(TextToSpeechEntity):
    """A Deepgram voice exposed to Home Assistant as a TTS entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry) -> None:
        """Bind the entity to its config entry."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Deepgram",
            model="Flux TTS",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def default_language(self) -> str:
        """Default language for this entity."""
        return DEFAULT_LANGUAGE

    @property
    def supported_languages(self) -> list[str]:
        """Languages this entity can speak. Widened in chapter 3 from the merged catalog."""
        return [DEFAULT_LANGUAGE]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict | None = None
    ) -> TtsAudioType:
        """Synthesize speech. Chapter 5 wires this to /v2/speak."""
        raise DeepgramRequestError(
            f"Synthesis is not implemented yet; chapter 5 wires {DEFAULT_VOICE} to /v2/speak"
        )
