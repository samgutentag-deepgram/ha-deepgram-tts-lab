"""The Deepgram TTS integration.

Chapter 1 of the build: the entry sets up, fetches the voice catalogs so a bad key or a dead
network fails loudly at setup rather than at the first spoken word, and forwards to the tts
platform.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import TIMEOUT_CATALOG, URL_MODELS_AURA, URL_MODELS_FLUX

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]

type DeepgramConfigEntry = Any  # narrowed in chapter 4 once the entry data shape is fixed


@dataclass(slots=True)
class DeepgramRuntimeData:
    """Everything the tts platform needs, built once at setup."""

    api_key: str
    catalogs: dict[str, dict]


async def _async_fetch_catalogs(session: ClientSession) -> dict[str, dict]:
    """Fetch both public model catalogs.

    Chapter 3 replaces this with catalog.py, which merges the two payloads into one
    family-tagged voice list. Here it exists only so setup fails when the API is unreachable.
    """
    payloads: dict[str, dict] = {}
    async with asyncio.timeout(TIMEOUT_CATALOG):
        for key, url in (("flux", URL_MODELS_FLUX), ("aura", URL_MODELS_AURA)):
            response = await session.get(url)
            response.raise_for_status()
            payloads[key] = await response.json()
    return payloads


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up Deepgram TTS from a config entry."""
    session = async_get_clientsession(hass)

    try:
        catalogs = await _async_fetch_catalogs(session)
    except (ClientError, TimeoutError) as err:
        # Letting this escape as a raw aiohttp error marks the entry failed with no retry.
        raise ConfigEntryNotReady(f"Could not reach {URL_MODELS_FLUX}: {err}") from err

    entry.runtime_data = DeepgramRuntimeData(
        api_key=entry.data[CONF_API_KEY],
        catalogs=catalogs,
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
