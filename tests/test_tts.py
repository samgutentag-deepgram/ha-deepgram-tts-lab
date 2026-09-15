"""Chapter 5's stop condition: the batch path, the Flux default, and no Flux for Spanish.

The streaming guard at the bottom is the load-bearing one. It fails the moment chapter 6 adds
`async_stream_tts_audio`, which is deliberate: nobody should merge the websocket path without
noticing that Home Assistant starts routing every Assist response down it.
"""

from typing import Any

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    Voice,
    async_get_media_source_audio,
    generate_media_source_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.api import DeepgramClient
from custom_components.deepgram_tts.catalog import async_fetch_catalog
from custom_components.deepgram_tts.const import (
    CONF_SPEED,
    CONF_VOICE,
    DEFAULT_VOICE,
    DOMAIN,
    URL_MODELS_AURA,
    URL_MODELS_FLUX,
    URL_SPEAK_AURA,
    URL_SPEAK_FLUX,
)
from custom_components.deepgram_tts.errors import DeepgramAuthError, DeepgramError
from custom_components.deepgram_tts.models import VoiceCatalog
from custom_components.deepgram_tts.tts import DeepgramTTSEntity

# Not valid audio, and starting with an ID3 tag on purpose: nothing in the entity is allowed to
# inspect or rewrite these bytes.
FAKE_AUDIO = b"ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90d\x00deadbeef\x00\x01\x02"

AURA_ES_VOICE = "aura-2-celeste-es"

# language -> the one Aura voice in multilingual_aura_payload that speaks it.
NON_ENGLISH_VOICES = {
    "es": "aura-2-celeste-es",
    "de": "aura-2-elara-de",
    "fr": "aura-2-agathe-fr",
    "nl": "aura-2-daphne-nl",
    "it": "aura-2-cinzia-it",
    "ja": "aura-2-fujin-ja",
}


@pytest.fixture
def mock_models(
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """Serve both public catalogs: one Flux voice plus one Aura voice per language."""
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(URL_MODELS_AURA, json=multilingual_aura_payload)


@pytest.fixture
def mock_api(mock_models: None, aioclient_mock: AiohttpClientMocker) -> None:
    """Serve the catalogs and a successful synthesis on both speak endpoints."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})
    aioclient_mock.post(URL_SPEAK_AURA, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})


@pytest.fixture
def fresh_entry() -> MockConfigEntry:
    """An entry as a fresh install leaves it: a key, and no voice chosen yet."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Flux (Haley)",
        data={"api_key": "test-key"},
    )


@pytest.fixture
async def catalog(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_models: None
) -> VoiceCatalog:
    # Async and dependent on aioclient_mock so the mock patch is installed before hass caches
    # its session. A sync fixture here gets a real session and fails as a DNS error.
    return await async_fetch_catalog(async_get_clientsession(hass))


def build_entity(
    hass: HomeAssistant, catalog: VoiceCatalog, entry: MockConfigEntry
) -> DeepgramTTSEntity:
    """Build the entity the way the platform does, without adding it to hass."""
    client = DeepgramClient(async_get_clientsession(hass), entry.data["api_key"])
    return DeepgramTTSEntity(entry, client, catalog)


def last_speak(aioclient_mock: AiohttpClientMocker):
    """Return (method, url, data, headers) for the most recent synthesis request."""
    for call in reversed(aioclient_mock.mock_calls):
        if call[0].upper() == "POST":
            return call
    raise AssertionError("no synthesis request was made")


def sent_model(aioclient_mock: AiohttpClientMocker) -> str:
    """Return the model the entity actually put on the wire."""
    return last_speak(aioclient_mock)[1].query["model"]


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Load one config entry and return the entity id it created."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_ids = hass.states.async_entity_ids("tts")
    assert len(entity_ids) == 1
    return entity_ids[0]


async def speak_through_hass(
    hass: HomeAssistant,
    entity_id: str,
    message: str,
    *,
    language: str | None = None,
    options: dict[str, Any] | None = None,
) -> tuple[str, bytes]:
    """Synthesize through the tts manager, the way Home Assistant itself does.

    cache=False keeps every call in a test reaching the entity: the manager keys its memory
    cache on message, language, options, and engine, and would otherwise replay the first one.
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


async def test_supported_languages_has_base_codes_only(
    hass: HomeAssistant, catalog: VoiceCatalog, mock_config_entry: MockConfigEntry
) -> None:
    """The hyphen regression, at the entity level. en and en-US must never both appear."""
    entity = build_entity(hass, catalog, mock_config_entry)

    assert "en" in entity.supported_languages
    assert "en-US" not in entity.supported_languages
    assert entity.default_language == "en"
    assert entity.default_language in entity.supported_languages
    assert not [code for code in entity.supported_languages if "-" in code]


async def test_flux_haley_is_the_default_on_a_fresh_install(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
    fresh_entry: MockConfigEntry,
) -> None:
    """HANDOFF 6.1, chapter 5's first verification. Assert the model sent, not the option."""
    entity_id = await setup_entry(hass, fresh_entry)

    await speak_through_hass(hass, entity_id, "Fresh install.")

    assert sent_model(aioclient_mock) == DEFAULT_VOICE
    assert sent_model(aioclient_mock) == "flux-haley-en"
    assert last_speak(aioclient_mock)[1].path == "/v2/speak"


@pytest.mark.parametrize(("language", "expected_voice"), NON_ENGLISH_VOICES.items())
async def test_non_english_never_resolves_to_flux(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    language: str,
    expected_voice: str,
) -> None:
    """Settled decision 4, once per language, because it is the one most likely to regress.

    The entry is configured with a Flux voice, which is the dangerous case: the configured
    voice is offered as the preference and has to be rejected for the language.
    """
    entity_id = await setup_entry(hass, mock_config_entry)

    await speak_through_hass(hass, entity_id, f"Hola en {language}.", language=language)

    model = sent_model(aioclient_mock)
    assert model.startswith("aura")
    assert not model.startswith("flux")
    assert model == expected_voice
    assert last_speak(aioclient_mock)[1].path == "/v1/speak"


async def test_per_call_voice_option_overrides_the_entry(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    entity_id = await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.options[CONF_VOICE] == DEFAULT_VOICE

    await speak_through_hass(
        hass, entity_id, "Otra voz.", language="es", options={ATTR_VOICE: AURA_ES_VOICE}
    )

    assert sent_model(aioclient_mock) == AURA_ES_VOICE


async def test_returned_audio_is_byte_identical(
    hass: HomeAssistant,
    mock_api: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The do-not-re-encode regression test. Also that the ID3 tag survives untouched."""
    entity_id = await setup_entry(hass, mock_config_entry)

    extension, audio = await speak_through_hass(hass, entity_id, "Byte for byte.")

    assert extension == "mp3"
    assert audio == FAKE_AUDIO
    assert len(audio) == len(FAKE_AUDIO)
    assert audio.startswith(b"ID3")


async def test_speed_reaches_the_query_for_flux(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    entity_id = await setup_entry(hass, mock_config_entry)

    await speak_through_hass(hass, entity_id, "Faster.", options={CONF_SPEED: 1.15})

    _, url, _, _ = last_speak(aioclient_mock)
    assert url.query["model"] == DEFAULT_VOICE
    assert url.query["speed"] == "1.15"


async def test_speed_is_not_sent_for_aura(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Aura has no speed parameter, so sending one is meaningless whoever drops it."""
    entity_id = await setup_entry(hass, mock_config_entry)

    await speak_through_hass(
        hass, entity_id, "Mas despacio.", language="es", options={CONF_SPEED: 1.15}
    )

    _, url, _, _ = last_speak(aioclient_mock)
    assert url.query["model"] == AURA_ES_VOICE
    assert "speed" not in url.query


async def test_configured_speed_is_the_default_option(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A speed set in the options flow applies without every call repeating it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Flux (Haley)",
        data={"api_key": "test-key"},
        options={CONF_VOICE: DEFAULT_VOICE, CONF_SPEED: 0.9},
    )
    entity_id = await setup_entry(hass, entry)

    await speak_through_hass(hass, entity_id, "Configured speed.")

    assert last_speak(aioclient_mock)[1].query["speed"] == "0.9"


async def test_preferred_format_wav_asks_for_linear16_in_a_wav_container(
    hass: HomeAssistant,
    mock_models: None,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """preferred_format is one string; Deepgram splits it into encoding and container."""
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/wav"})
    entity_id = await setup_entry(hass, mock_config_entry)

    extension, audio = await speak_through_hass(
        hass, entity_id, "In a wav.", options={ATTR_PREFERRED_FORMAT: "wav"}
    )

    _, url, _, _ = last_speak(aioclient_mock)
    assert url.query["encoding"] == "linear16"
    assert url.query["container"] == "wav"
    # Same extension back means HA's _async_convert_audio never runs, which is the whole point.
    assert extension == "wav"
    assert audio == FAKE_AUDIO


async def test_unmapped_preferred_format_sends_no_encoding(
    hass: HomeAssistant,
    catalog: VoiceCatalog,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An encoding Deepgram does not know is rejected outright, so ask for nothing instead.

    Called directly rather than through the manager: an unmapped format means HA converts, and
    the conversion is a real ffmpeg pass that would choke on this fixture's fake audio.
    """
    aioclient_mock.post(URL_SPEAK_FLUX, content=FAKE_AUDIO, headers={"Content-Type": "audio/mpeg"})
    entity = build_entity(hass, catalog, mock_config_entry)
    assert ATTR_PREFERRED_FORMAT in (entity.supported_options or [])

    extension, _ = await entity.async_get_tts_audio(
        "Unknown format.", "en", {ATTR_PREFERRED_FORMAT: "mulaw"}
    )

    _, url, _, _ = last_speak(aioclient_mock)
    assert "encoding" not in url.query
    assert "container" not in url.query
    # mp3 back against a mulaw request is what hands the conversion to HA on purpose.
    assert extension == "mp3"


async def test_auth_failure_propagates_untouched(
    hass: HomeAssistant,
    catalog: VoiceCatalog,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """DeepgramAuthError, not a generic failure. An expired key must stay distinguishable."""
    aioclient_mock.post(
        URL_SPEAK_FLUX,
        status=401,
        json={"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials."},
    )
    entity = build_entity(hass, catalog, mock_config_entry)

    with pytest.raises(DeepgramAuthError):
        await entity.async_get_tts_audio("Expired key.", "en", {})


async def test_unspeakable_language_raises_a_typed_error_naming_it(
    hass: HomeAssistant, catalog: VoiceCatalog, mock_config_entry: MockConfigEntry
) -> None:
    entity = build_entity(hass, catalog, mock_config_entry)

    with pytest.raises(DeepgramError, match="pt"):
        await entity.async_get_tts_audio("Bom dia.", "pt", {})


async def test_supported_voices_are_usable_voice_objects(
    hass: HomeAssistant, catalog: VoiceCatalog, mock_config_entry: MockConfigEntry
) -> None:
    """Including one Aura voice whose label came from chapter 3's null display_name fallback."""
    entity = build_entity(hass, catalog, mock_config_entry)

    english = entity.async_get_supported_voices("en")
    assert english is not None
    assert all(isinstance(voice, Voice) for voice in english)
    assert all(voice.voice_id and voice.name for voice in english)
    assert Voice("flux-haley-en", "Haley") in english
    # aura-2-asteria-en carries display_name: null in the payload, so "Asteria" is the
    # title-cased `name` fallback, which is the normal path for most of the live Aura list.
    assert Voice("aura-2-asteria-en", "Asteria") in english

    # A regional code resolves to the same list as its base code.
    assert entity.async_get_supported_voices("en-US") == english


async def test_supported_voices_is_none_for_an_unknown_language(
    hass: HomeAssistant, catalog: VoiceCatalog, mock_config_entry: MockConfigEntry
) -> None:
    """None, not []. An empty list reads as a restriction to no voices at all."""
    entity = build_entity(hass, catalog, mock_config_entry)

    assert entity.async_get_supported_voices("pt") is None


async def test_streaming_input_is_not_supported_yet(
    hass: HomeAssistant, catalog: VoiceCatalog, mock_config_entry: MockConfigEntry
) -> None:
    """The guard on chapter 6.

    Home Assistant auto-detects streaming by comparing the subclass method against the base
    one, so defining async_stream_tts_audio at all is the opt-in. Chapter 5 has no websocket,
    so this must read False, and this test is expected to fail when chapter 6 lands.
    """
    entity = build_entity(hass, catalog, mock_config_entry)

    assert entity.async_supports_streaming_input() is False
    assert "async_stream_tts_audio" not in vars(DeepgramTTSEntity)


async def test_two_entries_get_distinguishable_entity_ids(
    hass: HomeAssistant,
    mock_api: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Chapter 1's naming assertion, kept working now that the entity does real work."""
    aura_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Aura (Celeste)",
        data={"api_key": "test-key-2"},
        options={CONF_VOICE: AURA_ES_VOICE},
    )
    mock_config_entry.add_to_hass(hass)
    aura_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert set(hass.states.async_entity_ids("tts")) == {
        "tts.deepgram_flux_haley",
        "tts.deepgram_aura_celeste",
    }


async def test_tts_speak_service_round_trip(
    hass: HomeAssistant,
    mock_api: None,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The real service, end to end: tts.speak, then fetch the stream it handed the player."""
    entity_id = await setup_entry(hass, mock_config_entry)
    played = async_mock_service(hass, "media_player", "play_media")

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
    extension, audio = await async_get_media_source_audio(hass, played[0].data["media_content_id"])

    assert extension == "mp3"
    assert audio == FAKE_AUDIO
    assert sent_model(aioclient_mock) == DEFAULT_VOICE
