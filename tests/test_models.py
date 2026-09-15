"""The language code split is the one thing in models.py that has bitten a real codebase."""

from custom_components.deepgram_tts.const import FAMILY_AURA, FAMILY_FLUX
from custom_components.deepgram_tts.models import VoiceInfo, family_for_model


def test_base_languages_splits_on_hyphen():
    voice = VoiceInfo(
        voice_id="aura-2-celeste-es",
        name="Celeste",
        family=FAMILY_AURA,
        languages=("es", "es-CO", "es-419"),
    )
    assert voice.base_languages == {"es"}


def test_base_languages_does_not_leak_regional_codes():
    voice = VoiceInfo(
        voice_id="flux-haley-en", name="Haley", family=FAMILY_FLUX, languages=("en", "en-US")
    )
    assert voice.base_languages == {"en"}
    assert "en-US" not in voice.base_languages


def test_family_routes_on_prefix():
    assert family_for_model("flux-haley-en") == FAMILY_FLUX
    assert family_for_model("aura-2-thalia-en") == FAMILY_AURA
    assert family_for_model("aura-asteria-en") == FAMILY_AURA
