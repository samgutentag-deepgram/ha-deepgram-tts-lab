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
