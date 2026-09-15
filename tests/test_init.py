"""Chapter 1's stop condition: the entry loads, and a dead catalog retries instead of failing."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.const import URL_MODELS_AURA, URL_MODELS_FLUX


@pytest.fixture
def mock_catalogs(
    aioclient_mock: AiohttpClientMocker, flux_models_payload: dict, aura_models_payload: dict
) -> None:
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(URL_MODELS_AURA, json=aura_models_payload)


async def test_entry_loads_and_unloads(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_catalogs: None
) -> None:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("tts")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unreachable_catalog_retries(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A dead catalog must land in SETUP_RETRY, not SETUP_ERROR."""
    aioclient_mock.get(URL_MODELS_FLUX, status=503)
    aioclient_mock.get(URL_MODELS_AURA, status=503)

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_two_entries_can_coexist(
    hass: HomeAssistant, mock_catalogs: None, mock_config_entry: MockConfigEntry
) -> None:
    """One Flux entity and one Aura entity side by side is a supported configuration."""
    second = MockConfigEntry(
        domain=mock_config_entry.domain,
        title="Deepgram Aura (Celeste)",
        data={"api_key": "test-key-2"},
        options={"voice": "aura-2-celeste-es"},
    )
    mock_config_entry.add_to_hass(hass)
    second.add_to_hass(hass)

    # Setting up the domain loads every entry it owns, which is the behavior under test:
    # neither entry aborts the other, because nothing claims a constant unique_id.
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids("tts")) == 2
