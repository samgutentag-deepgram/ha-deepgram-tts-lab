"""Chapter 4's stop condition: a key is verified, a voice is picked, and a typo is recoverable.

Every authenticated call is mocked. There is no Deepgram API key on this machine, so nothing
here proves what the live /v2/speak does with a real key.
"""

from typing import Any
from unittest.mock import patch

from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.const import (
    CONF_SPEED,
    CONF_VOICE,
    DEFAULT_SPEED,
    DEFAULT_VOICE,
    DOMAIN,
    URL_MODELS_AURA,
    URL_MODELS_FLUX,
    URL_SPEAK_FLUX,
)

# display_name is null for this one in the shared fixture, so its label comes from the
# title-cased bare name. That fallback is the normal path for 61 of the 102 live Aura voices.
AURA_VOICE = "aura-2-asteria-en"
LEGACY_AURA_VOICE = "aura-asteria-en"

# async_verify_key throws the audio away, so the bytes only have to be bytes.
VERIFY_AUDIO = b"\xff\xfb\x90d\x00verify"


def _legacy_asteria() -> dict[str, Any]:
    """A legacy `aura` entry whose fallback name collides with the aura-2 one.

    Both title-case to "Asteria" with the same family and the same accent, which is why the
    picker label has to carry the voice id.
    """
    return {
        "name": "asteria",
        "canonical_name": LEGACY_AURA_VOICE,
        "architecture": "aura",
        "languages": ["en", "en-US"],
        "version": "2024-01-01.0",
        "metadata": {"accent": "Neutral", "age": "Adult", "display_name": None},
    }


def _mock_catalogs(
    aioclient_mock: AiohttpClientMocker, flux_payload: dict, aura_payload: dict
) -> None:
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_payload)
    aioclient_mock.get(URL_MODELS_AURA, json=aura_payload)


def _mock_everything(
    aioclient_mock: AiohttpClientMocker, flux_payload: dict, aura_payload: dict
) -> None:
    aioclient_mock.post(
        URL_SPEAK_FLUX, content=VERIFY_AUDIO, headers={"Content-Type": "audio/mpeg"}
    )
    _mock_catalogs(aioclient_mock, flux_payload, aura_payload)


@pytest.fixture
async def deepgram(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> AiohttpClientMocker:
    """A key that verifies plus both public catalogs.

    Async, and dependent on aioclient_mock, so the mock patch is installed before hass caches
    an aiohttp session. A sync fixture here gets a real session and tries to resolve DNS.
    """
    _mock_everything(aioclient_mock, flux_models_payload, multilingual_aura_payload)
    return aioclient_mock


def _fields(result: dict) -> dict[str, Any]:
    """Map the form's field names to their schema values."""
    return {str(key): value for key, value in result["data_schema"].schema.items()}


def _voice_selector(result: dict) -> Any:
    return _fields(result)[CONF_VOICE]


def _labels(result: dict) -> dict[str, str]:
    """Map voice id to the label the picker shows, in the order the picker shows them."""
    return {
        option["value"]: option["label"] for option in _voice_selector(result).config["options"]
    }


def _default_of(result: dict, field: str) -> Any:
    for key in result["data_schema"].schema:
        if str(key) == field:
            return key.default()
    raise AssertionError(f"no {field} field in the form")


async def _start(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _submit(hass: HomeAssistant, result: dict, user_input: dict) -> dict:
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def _add_voice(hass: HomeAssistant, api_key: str, voice_id: str) -> dict:
    """Walk the whole flow and return the final result."""
    result = await _submit(hass, await _start(hass), {CONF_API_KEY: api_key})
    return await _submit(hass, result, {CONF_VOICE: voice_id})


async def test_happy_path_creates_the_entry(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _submit(hass, result, {CONF_API_KEY: "good-key"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "voice"
    assert not result["errors"]
    assert _default_of(result, CONF_VOICE) == DEFAULT_VOICE

    result = await _submit(hass, result, {CONF_VOICE: DEFAULT_VOICE})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Deepgram Flux (Haley)"
    assert result["data"] == {CONF_API_KEY: "good-key"}
    assert result["options"] == {CONF_VOICE: DEFAULT_VOICE}

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == DEFAULT_VOICE
    assert entry.state is ConfigEntryState.LOADED


async def test_picker_is_a_flux_first_searchable_dropdown(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    """138 voices in one list only works if the order is deliberate and typing is allowed."""
    result = await _submit(hass, await _start(hass), {CONF_API_KEY: "good-key"})

    config = _voice_selector(result).config
    assert config["mode"] == "dropdown"
    assert config["custom_value"] is False
    # Frontend sorting would alphabetize the labels and lose the Flux-first order.
    assert config["sort"] is False

    ordered = list(_labels(result))
    assert ordered[0] == DEFAULT_VOICE
    assert ordered[1] == AURA_VOICE, "English Aura sorts ahead of the other languages"
    # Then the rest by language code, so the tail groups instead of interleaving.
    assert ordered[2:] == [
        "aura-2-elara-de",
        "aura-2-celeste-es",
        "aura-2-agathe-fr",
        "aura-2-cinzia-it",
        "aura-2-fujin-ja",
        "aura-2-daphne-nl",
    ]


async def test_aura_fallback_label_is_usable_and_unique(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """The null display_name fallback is the normal path, so its label has to read correctly."""
    multilingual_aura_payload["tts"].append(_legacy_asteria())
    _mock_everything(aioclient_mock, flux_models_payload, multilingual_aura_payload)

    result = await _submit(hass, await _start(hass), {CONF_API_KEY: "good-key"})
    labels = _labels(result)

    assert labels[AURA_VOICE] == "Asteria (Aura, Neutral) [aura-2-asteria-en]"
    assert labels[LEGACY_AURA_VOICE] == "Asteria (Aura, Neutral) [aura-asteria-en]"
    assert labels[AURA_VOICE] != labels[LEGACY_AURA_VOICE]
    assert len(set(labels.values())) == len(labels)
    for label in labels.values():
        assert label
        assert "None" not in label

    assert labels[DEFAULT_VOICE] == "Haley (Flux, American) [flux-haley-en]"
    # Non-English voices carry their language code, because the name says nothing about it.
    assert labels["aura-2-celeste-es"] == "Celeste (Aura, Neutral, es) [aura-2-celeste-es]"


async def test_an_aura_voice_titles_its_entry_from_the_fallback_name(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    result = await _add_voice(hass, "good-key", AURA_VOICE)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Deepgram Aura (Asteria)"
    assert result["options"] == {CONF_VOICE: AURA_VOICE}


async def test_rejected_key_shows_the_form_and_then_recovers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """Recovery is the behavior that matters: a typo is one correction away, not a restart."""
    aioclient_mock.post(
        URL_SPEAK_FLUX,
        status=401,
        json={"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials."},
    )

    result = await _start(hass)
    result = await _submit(hass, result, {CONF_API_KEY: "typo"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    assert not hass.config_entries.async_entries(DOMAIN)

    aioclient_mock.clear_requests()
    _mock_everything(aioclient_mock, flux_models_payload, multilingual_aura_payload)

    result = await _submit(hass, result, {CONF_API_KEY: "good-key"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "voice"

    result = await _submit(hass, result, {CONF_VOICE: DEFAULT_VOICE})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "good-key"}


async def test_network_failure_shows_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL_SPEAK_FLUX, exc=ClientConnectionError("no route to host"))

    result = await _submit(hass, await _start(hass), {CONF_API_KEY: "good-key"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_catalog_failure_shows_cannot_connect_rather_than_aborting(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The key is fine and the catalogs are not. That is transient, so the form comes back."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=VERIFY_AUDIO)
    aioclient_mock.get(URL_MODELS_FLUX, status=503)
    aioclient_mock.get(URL_MODELS_AURA, status=503)

    result = await _submit(hass, await _start(hass), {CONF_API_KEY: "good-key"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unexpected_exception_shows_unknown_without_leaking(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.deepgram_tts.config_flow.DeepgramClient.async_verify_key",
        side_effect=ValueError("kaboom at line 41"),
    ):
        result = await _submit(hass, await _start(hass), {CONF_API_KEY: "good-key"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    rendered = str(result)
    assert "kaboom" not in rendered
    assert "Traceback" not in rendered


async def test_the_same_voice_twice_aborts(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    await _add_voice(hass, "good-key", DEFAULT_VOICE)
    await hass.async_block_till_done()

    result = await _add_voice(hass, "good-key", DEFAULT_VOICE)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_a_second_different_voice_succeeds(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    """The test that proves the unique_id decision: one voice per entry, many entries."""
    first = await _add_voice(hass, "good-key", DEFAULT_VOICE)
    await hass.async_block_till_done()
    second = await _add_voice(hass, "good-key", AURA_VOICE)
    await hass.async_block_till_done()

    assert first["type"] is FlowResultType.CREATE_ENTRY
    assert second["type"] is FlowResultType.CREATE_ENTRY

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {entry.unique_id for entry in entries} == {DEFAULT_VOICE, AURA_VOICE}
    assert {entry.title for entry in entries} == {
        "Deepgram Flux (Haley)",
        "Deepgram Aura (Asteria)",
    }


async def _loaded_entry(
    hass: HomeAssistant, voice_id: str, options: dict | None = None
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Deepgram ({voice_id})",
        data={CONF_API_KEY: "test-key"},
        options=options if options is not None else {CONF_VOICE: voice_id},
        unique_id=voice_id,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_options_flow_round_trips_and_reloads(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    """Changing options has to reload the entry through the listener __init__ registered."""
    entry = await _loaded_entry(hass, DEFAULT_VOICE)
    setups = deepgram.call_count

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert _default_of(result, CONF_VOICE) == DEFAULT_VOICE
    assert _default_of(result, CONF_SPEED) == DEFAULT_SPEED

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_VOICE: DEFAULT_VOICE, CONF_SPEED: 1.25}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_VOICE: DEFAULT_VOICE, CONF_SPEED: 1.25}
    assert entry.state is ConfigEntryState.LOADED
    # Exactly two more calls: the options form reuses the catalog the loaded entry already
    # holds, and the reload's setup fetches both catalogs once.
    assert deepgram.call_count == setups + 2


async def test_speed_is_offered_for_flux(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    entry = await _loaded_entry(hass, DEFAULT_VOICE)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert set(_fields(result)) == {CONF_VOICE, CONF_SPEED}
    speed = _fields(result)[CONF_SPEED].config
    assert speed["min"] == 0.5
    assert speed["max"] == 1.5
    assert speed["step"] == 0.05


async def test_speed_is_not_offered_for_aura(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    """Aura has no speed parameter at all, so offering the field would be a lie."""
    entry = await _loaded_entry(hass, AURA_VOICE)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert set(_fields(result)) == {CONF_VOICE}
    assert CONF_SPEED not in _fields(result)


async def test_switching_from_flux_to_aura_drops_the_stored_speed(
    hass: HomeAssistant, deepgram: AiohttpClientMocker
) -> None:
    entry = await _loaded_entry(hass, DEFAULT_VOICE, {CONF_VOICE: DEFAULT_VOICE, CONF_SPEED: 1.4})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_VOICE: AURA_VOICE, CONF_SPEED: 1.4}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_VOICE: AURA_VOICE}


async def test_options_abort_when_the_voice_list_is_unreachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An entry in SETUP_RETRY has no runtime catalog, so the options flow fetches one."""
    aioclient_mock.get(URL_MODELS_FLUX, status=503)
    aioclient_mock.get(URL_MODELS_AURA, status=503)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Flux (Haley)",
        data={CONF_API_KEY: "test-key"},
        options={CONF_VOICE: DEFAULT_VOICE},
        unique_id=DEFAULT_VOICE,
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
