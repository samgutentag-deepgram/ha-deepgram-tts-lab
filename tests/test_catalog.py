"""Chapter 3's stop condition: two catalogs merge, and no non-English pipeline reaches Flux."""

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.deepgram_tts.catalog import (
    async_fetch_catalog,
    resolve_voice,
    supported_languages,
    voices_for_language,
)
from custom_components.deepgram_tts.const import (
    DEFAULT_VOICE,
    FAMILY_AURA,
    FAMILY_FLUX,
    URL_MODELS_AURA,
    URL_MODELS_FLUX,
)
from custom_components.deepgram_tts.errors import DeepgramConnectionError
from custom_components.deepgram_tts.models import VoiceCatalog, VoiceInfo


async def _fetch(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_payload: dict,
    aura_payload: dict,
) -> VoiceCatalog:
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_payload)
    aioclient_mock.get(URL_MODELS_AURA, json=aura_payload)
    return await async_fetch_catalog(async_get_clientsession(hass))


async def test_merge_keeps_both_families(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    aura_models_payload: dict,
) -> None:
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, aura_models_payload)

    assert set(catalog.voices) == {"flux-haley-en", "aura-2-celeste-es"}

    haley = catalog.get("flux-haley-en")
    assert haley is not None
    assert haley.family == FAMILY_FLUX
    assert haley.is_flux
    assert haley.name == "Haley"
    assert haley.languages == ("en", "en-US")
    assert haley.accent == "American"
    assert haley.age == "Young Adult"
    assert haley.tags == ("feminine", "professional")
    assert haley.sample_url == "https://example.invalid/haley.wav"

    celeste = catalog.get("aura-2-celeste-es")
    assert celeste is not None
    assert celeste.family == FAMILY_AURA
    assert not celeste.is_flux
    assert celeste.name == "Celeste"


async def test_null_display_name_falls_back_to_title_cased_name(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """61 of the 102 live Aura entries carry display_name as null, so this path is normal."""
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    asteria = catalog.get("aura-2-asteria-en")
    assert asteria is not None
    assert asteria.name == "Asteria"


async def test_supported_languages_returns_base_codes_only(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """The regression test for the hyphen bug that was wrong in five places before."""
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    result = supported_languages(catalog)

    assert "en" in result
    assert "en-US" not in result
    assert result == ["de", "en", "es", "fr", "it", "ja", "nl"]
    assert result == sorted(result)
    assert not any("-" in code for code in result)


async def test_regional_input_matches_on_base_code(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    aura_models_payload: dict,
) -> None:
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, aura_models_payload)

    found = voices_for_language(catalog, "en-US")

    assert [voice.voice_id for voice in found] == ["flux-haley-en"]
    # The Spanish voice reports es-CO, and en-US must not reach it.
    assert [voice.voice_id for voice in voices_for_language(catalog, "es-419")] == [
        "aura-2-celeste-es"
    ]


async def test_flux_sorts_before_aura_for_english(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """The picker has to read Flux first, and has to be stable between restarts."""
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    found = voices_for_language(catalog, "en")

    assert [voice.voice_id for voice in found] == ["flux-haley-en", "aura-2-asteria-en"]
    assert [voice.family for voice in found] == [FAMILY_FLUX, FAMILY_AURA]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("es", "aura-2-celeste-es"),
        ("de", "aura-2-elara-de"),
        ("fr", "aura-2-agathe-fr"),
        ("nl", "aura-2-daphne-nl"),
        ("it", "aura-2-cinzia-it"),
        ("ja", "aura-2-fujin-ja"),
    ],
)
async def test_non_english_never_resolves_to_flux(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
    language: str,
    expected: str,
) -> None:
    """Settled decision 4, per language. Every Flux voice is English."""
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    voice = resolve_voice(catalog, language, None)

    assert voice is not None
    assert voice.voice_id == expected
    assert voice.family == FAMILY_AURA
    assert voice.is_flux is False


async def test_english_resolves_to_the_default_voice(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    voice = resolve_voice(catalog, "en", None)

    assert voice is not None
    assert voice.voice_id == DEFAULT_VOICE
    assert voice.is_flux


async def test_preferred_voice_wins_when_it_can_speak_the_language(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    voice = resolve_voice(catalog, "en-US", "aura-2-asteria-en")

    assert voice is not None
    assert voice.voice_id == "aura-2-asteria-en"


async def test_preferred_flux_voice_is_refused_for_spanish(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    multilingual_aura_payload: dict,
) -> None:
    """A stored Flux preference must not follow a Spanish pipeline into /v2/speak."""
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, multilingual_aura_payload)

    voice = resolve_voice(catalog, "es", DEFAULT_VOICE)

    assert voice is not None
    assert voice.voice_id != DEFAULT_VOICE
    assert voice.voice_id == "aura-2-celeste-es"
    assert voice.is_flux is False


async def test_unknown_language_resolves_to_nothing(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    aura_models_payload: dict,
) -> None:
    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, aura_models_payload)

    assert resolve_voice(catalog, "fi", None) is None
    assert voices_for_language(catalog, "fi") == []


async def test_entry_without_canonical_name_is_skipped(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    aura_models_payload: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One malformed entry must never take the rest of the catalog with it."""
    flux_models_payload["tts"].insert(
        0, {"name": "nameless", "architecture": "flux-tts", "languages": ["en"]}
    )

    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, aura_models_payload)

    assert set(catalog.voices) == {"flux-haley-en", "aura-2-celeste-es"}
    assert "no canonical_name" in caplog.text


async def test_a_shared_voice_id_keeps_flux_and_warns(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
    aura_models_payload: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The endpoints do not overlap today, so a collision means one changed shape."""
    intruder = dict(flux_models_payload["tts"][0])
    intruder["architecture"] = "aura-2"
    intruder["metadata"] = {"display_name": "Impostor"}
    aura_models_payload["tts"].append(intruder)

    catalog = await _fetch(hass, aioclient_mock, flux_models_payload, aura_models_payload)

    haley = catalog.get("flux-haley-en")
    assert haley is not None
    assert haley.family == FAMILY_FLUX
    assert haley.name == "Haley"
    assert "appears in both catalogs" in caplog.text


async def test_fetch_failure_raises_a_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, aura_models_payload: dict
) -> None:
    """__init__ turns this into ConfigEntryNotReady, so it must not be a raw aiohttp error."""
    aioclient_mock.get(URL_MODELS_FLUX, exc=ClientError("boom"))
    aioclient_mock.get(URL_MODELS_AURA, json=aura_models_payload)

    with pytest.raises(DeepgramConnectionError):
        await async_fetch_catalog(async_get_clientsession(hass))


async def test_server_error_raises_a_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, flux_models_payload: dict
) -> None:
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(URL_MODELS_AURA, status=503)

    with pytest.raises(DeepgramConnectionError):
        await async_fetch_catalog(async_get_clientsession(hass))


# --- what the skeptic pass found, and what would have caught it -------------------------


def _catalog(*voices: VoiceInfo) -> VoiceCatalog:
    return VoiceCatalog(voices={voice.voice_id: voice for voice in voices})


MISLABELED_FLUX_ES = VoiceInfo(
    voice_id="flux-rogue-es",
    name="Rogue",
    family=FAMILY_FLUX,
    languages=("es", "es-MX"),
)
REAL_AURA_ES = VoiceInfo(
    voice_id="aura-2-celeste-es",
    name="Celeste",
    family=FAMILY_AURA,
    languages=("es", "es-CO"),
)


def test_a_mislabeled_flux_voice_is_refused_even_when_it_is_the_preference():
    """The reproduced counterexample to a ledger claim, now a test.

    The ledger said settled decision 4 "survives a catalog that is wrong about itself." It did
    not. The last-resort branch was guarded on the language, but the preferred-voice branch was
    guarded on neither the language nor the family, so it trusted the catalog completely and a
    Flux entry claiming `es` came straight back for a Spanish pipeline.

    Every Flux voice is English. A Flux entry claiming Spanish is a labeling error, not a
    capability, so it has to be refused whoever asked for it.
    """
    catalog = _catalog(MISLABELED_FLUX_ES, REAL_AURA_ES)

    voice = resolve_voice(catalog, "es", "flux-rogue-es")

    assert voice is not None
    assert voice.is_flux is False
    assert voice.voice_id == "aura-2-celeste-es"


def test_a_mislabeled_flux_voice_is_refused_even_as_the_only_candidate():
    """Nothing beats no voice at all, when the alternative is the wrong language."""
    catalog = _catalog(MISLABELED_FLUX_ES)

    assert resolve_voice(catalog, "es", "flux-rogue-es") is None
    assert resolve_voice(catalog, "es", None) is None


@pytest.mark.parametrize("language", ["es", "de", "fr", "nl", "it", "ja"])
def test_the_family_guard_is_load_bearing_for_every_language(language: str):
    """Chapter 3's six-language test passed with the family guard deleted.

    Its fixture gave each language exactly one voice, and that voice was Aura, so "first
    non-Flux candidate" and "first candidate" were the same object and the guard could be
    removed without anything failing. Here each language has a Flux voice that sorts first, so
    deleting the guard returns Flux and the test fails.
    """
    rogue = VoiceInfo(
        voice_id=f"flux-rogue-{language}",
        name="Aaa Rogue",  # sorts first within its family, and Flux sorts before Aura
        family=FAMILY_FLUX,
        languages=(language,),
    )
    real = VoiceInfo(
        voice_id=f"aura-2-real-{language}",
        name="Zzz Real",
        family=FAMILY_AURA,
        languages=(language,),
    )
    catalog = _catalog(rogue, real)

    assert voices_for_language(catalog, language)[0].is_flux is True

    voice = resolve_voice(catalog, language, None)

    assert voice is not None
    assert voice.is_flux is False
    assert voice.voice_id == f"aura-2-real-{language}"


def test_a_flux_voice_is_still_allowed_for_english():
    """The guard is on the language, not a blanket refusal. English is what Flux is for."""
    haley = VoiceInfo(
        voice_id=DEFAULT_VOICE, name="Haley", family=FAMILY_FLUX, languages=("en", "en-US")
    )
    catalog = _catalog(haley)

    voice = resolve_voice(catalog, "en-GB", DEFAULT_VOICE)

    assert voice is not None
    assert voice.voice_id == DEFAULT_VOICE


async def test_a_body_that_is_not_json_retries_instead_of_failing_the_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    flux_models_payload: dict,
) -> None:
    """A 200 carrying an error page used to escape as ValueError, which means no retry.

    aiohttp raises ContentTypeError, a ClientError, when the content type is wrong. A JSON
    content type with a malformed body raises ValueError instead, and that escaped
    async_setup_entry as a raw exception and put the entry in SETUP_ERROR. A proxy serving an
    error page is transient, so the entry has to retry.
    """
    aioclient_mock.get(URL_MODELS_FLUX, json=flux_models_payload)
    aioclient_mock.get(
        URL_MODELS_AURA,
        text="<html>502 Bad Gateway</html>",
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(DeepgramConnectionError, match="not JSON"):
        await async_fetch_catalog(async_get_clientsession(hass))
