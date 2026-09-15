"""Shared fixtures."""

from collections.abc import Generator

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.deepgram_tts.const import CONF_VOICE, DEFAULT_VOICE, DOMAIN

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry holding a Flux voice."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Deepgram Flux (Haley)",
        data={"api_key": "test-key"},
        options={CONF_VOICE: DEFAULT_VOICE},
    )


@pytest.fixture
def flux_models_payload() -> dict:
    """A trimmed /v2/models response, same shape as the real one."""
    return {
        "stt": [],
        "languages": {"en": "English"},
        "tts": [
            {
                "name": "haley",
                "canonical_name": "flux-haley-en",
                "architecture": "flux-tts",
                "languages": ["en", "en-US"],
                "version": "2026-08-12.0",
                "uuid": "00000000-0000-0000-0000-000000000001",
                "metadata": {
                    "accent": "American",
                    "age": "Young Adult",
                    "display_name": "Haley",
                    "tags": ["feminine", "professional"],
                    "sample": "https://example.invalid/haley.wav",
                },
            }
        ],
    }


@pytest.fixture
def aura_models_payload() -> dict:
    """A trimmed /v1/models response, same shape as the real one."""
    return {
        "stt": [],
        "languages": {"es": "Spanish"},
        "tts": [
            {
                "name": "celeste",
                "canonical_name": "aura-2-celeste-es",
                "architecture": "aura-2",
                "languages": ["es", "es-CO"],
                "version": "2025-04-01.0",
                "uuid": "00000000-0000-0000-0000-000000000002",
                "metadata": {
                    "accent": "Colombian",
                    "age": "Adult",
                    "display_name": "Celeste",
                    "tags": ["feminine", "clear"],
                    "sample": "https://example.invalid/celeste.wav",
                },
            }
        ],
    }


@pytest.fixture
def anyio_backend() -> Generator[str]:
    """Run async tests on asyncio."""
    yield "asyncio"


def _aura_entry(
    name: str, canonical_name: str, languages: list[str], *, display_name: str | None = None
) -> dict:
    """One /v1/models tts entry.

    display_name defaults to None because that is what the live catalog does for 61 of its
    102 Aura entries: the key is present and the value is null.
    """
    return {
        "name": name,
        "canonical_name": canonical_name,
        "architecture": "aura-2",
        "languages": languages,
        "version": "2025-04-01.0",
        "metadata": {
            "accent": "Neutral",
            "age": "Adult",
            "display_name": display_name,
            "tags": ["feminine"],
            "sample": f"https://example.invalid/{name}.wav",
        },
    }


@pytest.fixture
def multilingual_aura_payload() -> dict:
    """A /v1/models response with one Aura voice per non-English language, plus English.

    Settled decision 4 says a non-English pipeline must never resolve to Flux, and every Flux
    voice is English, so that rule needs one Aura voice per language to be testable per
    language rather than once.
    """
    return {
        "stt": [],
        "languages": {"en": "English", "es": "Spanish"},
        "tts": [
            _aura_entry("celeste", "aura-2-celeste-es", ["es", "es-CO"], display_name="Celeste"),
            _aura_entry("elara", "aura-2-elara-de", ["de", "de-DE"], display_name="Elara"),
            _aura_entry("agathe", "aura-2-agathe-fr", ["fr", "fr-FR"], display_name="Agathe"),
            _aura_entry("daphne", "aura-2-daphne-nl", ["nl", "nl-NL"], display_name="Daphne"),
            _aura_entry("cinzia", "aura-2-cinzia-it", ["it", "it-IT"], display_name="Cinzia"),
            _aura_entry("fujin", "aura-2-fujin-ja", ["ja", "ja-JP"], display_name="Fujin"),
            # display_name null on purpose, so the title-cased fallback is exercised.
            _aura_entry("asteria", "aura-2-asteria-en", ["en", "en-US"]),
        ],
    }
