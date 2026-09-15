"""The Deepgram TTS integration.

The entry sets up, fetches the voice catalog so a dead network fails loudly at setup rather
than at the first spoken word, and forwards to the tts platform.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .catalog import async_fetch_catalog
from .errors import DeepgramConnectionError
from .models import VoiceCatalog

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]

type DeepgramConfigEntry = Any  # narrowed in chapter 4 once the entry data shape is fixed


@dataclass(slots=True)
class DeepgramRuntimeData:
    """Everything the tts platform needs, built once at setup."""

    api_key: str
    catalog: VoiceCatalog


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up Deepgram TTS from a config entry."""
    session = async_get_clientsession(hass)

    try:
        catalog = await async_fetch_catalog(session)
    except DeepgramConnectionError as err:
        # Letting a fetch failure escape marks the entry failed with no retry.
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = DeepgramRuntimeData(
        api_key=entry.data[CONF_API_KEY],
        catalog=catalog,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
