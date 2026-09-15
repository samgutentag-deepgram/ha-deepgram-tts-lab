"""Reproductions for catalog.py: resolve_voice edges and the error types a fetch can produce.

    .venv/bin/python docs/review/repro/repro_catalog.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/Users/samgutentag/LABS/ha-deepgram-tts-lab/.claude/worktrees/agent-a72565c57ade8ce4a")

from custom_components.deepgram_tts.catalog import (  # noqa: E402
    resolve_voice,
    supported_languages,
    voices_for_language,
)
from custom_components.deepgram_tts.const import FAMILY_AURA, FAMILY_FLUX  # noqa: E402
from custom_components.deepgram_tts.models import VoiceCatalog, VoiceInfo  # noqa: E402


def flux(voice_id: str, name: str, languages: tuple[str, ...]) -> VoiceInfo:
    return VoiceInfo(voice_id=voice_id, name=name, family=FAMILY_FLUX, languages=languages)


def aura(voice_id: str, name: str, languages: tuple[str, ...]) -> VoiceInfo:
    return VoiceInfo(voice_id=voice_id, name=name, family=FAMILY_AURA, languages=languages)


def catalog(*voices: VoiceInfo) -> VoiceCatalog:
    return VoiceCatalog(voices={v.voice_id: v for v in voices})


def show(label: str, result) -> None:
    if isinstance(result, VoiceInfo):
        print(f"  {label:<62} -> {result.voice_id} (family={result.family})")
    else:
        print(f"  {label:<62} -> {result!r}")


print(f"python {sys.version.split()[0]}\n")

# --- settled decision 4: a non-English language must never resolve to Flux ---------------

print("1. a catalog that mislabels a Flux voice with Spanish")
mislabeled = catalog(
    flux("flux-haley-en", "Haley", ("en", "en-US")),
    flux("flux-rogue-es", "Rogue", ("es", "es-419")),  # Deepgram wrong about itself
    aura("aura-2-celeste-es", "Celeste", ("es", "es-CO")),
)
show('resolve_voice(lang="es", preferred=None)', resolve_voice(mislabeled, "es", None))
show(
    'resolve_voice(lang="es", preferred="flux-rogue-es")   <-- stored preference',
    resolve_voice(mislabeled, "es", "flux-rogue-es"),
)
show(
    'resolve_voice(lang="es", preferred="flux-haley-en")',
    resolve_voice(mislabeled, "es", "flux-haley-en"),
)

print("\n2. the same mislabel with no Aura voice for that language at all")
no_aura = catalog(
    flux("flux-haley-en", "Haley", ("en", "en-US")),
    flux("flux-rogue-es", "Rogue", ("es", "es-419")),
)
show('resolve_voice(lang="es", preferred=None)', resolve_voice(no_aura, "es", None))
show(
    'resolve_voice(lang="es", preferred="flux-rogue-es")',
    resolve_voice(no_aura, "es", "flux-rogue-es"),
)

print("\n3. the last-resort branch: English with no Aura English voice")
english_only_flux = catalog(
    flux("flux-haley-en", "Haley", ("en", "en-US")),
    aura("aura-2-celeste-es", "Celeste", ("es", "es-CO")),
)
show('resolve_voice(lang="en", preferred=None)', resolve_voice(english_only_flux, "en", None))
no_default = catalog(
    flux("flux-bree-en", "Bree", ("en", "en-GB")),
    aura("aura-2-celeste-es", "Celeste", ("es", "es-CO")),
)
show(
    'resolve_voice(lang="en", preferred=None) with DEFAULT_VOICE absent',
    resolve_voice(no_default, "en", None),
)

print("\n4. degenerate inputs")
empty = VoiceCatalog(voices={})
show("resolve_voice(empty catalog, \"en\", None)", resolve_voice(empty, "en", None))
show("resolve_voice(empty catalog, \"\", None)", resolve_voice(empty, "", None))
show('resolve_voice(normal, "", None)', resolve_voice(english_only_flux, "", None))
show('resolve_voice(normal, "EN-us", None)', resolve_voice(english_only_flux, "EN-us", None))
show('resolve_voice(normal, "en-US-x-custom", None)', resolve_voice(english_only_flux, "en-US-x-custom", None))
show('voices_for_language(normal, "EN-us")', [v.voice_id for v in voices_for_language(english_only_flux, "EN-us")])
show("supported_languages(empty catalog)", supported_languages(empty))

print("\n5. a catalog whose language codes are upper case (the reverse of the lowercasing)")
shouty = catalog(aura("aura-2-loud-en", "Loud", ("EN", "EN-US")))
show('voices_for_language(shouty, "en")', [v.voice_id for v in voices_for_language(shouty, "en")])
show('resolve_voice(shouty, "en", None)', resolve_voice(shouty, "en", None))
show("supported_languages(shouty)", supported_languages(shouty))

print("\n6. a preferred voice that is not a string")
for bad in (123, 1.5, True, ["flux-haley-en"], {"a": 1}):
    try:
        result = resolve_voice(english_only_flux, "en", bad)
    except Exception as err:  # noqa: BLE001
        show(f"preferred={bad!r}", f"{type(err).__name__}: {err}")
    else:
        show(f"preferred={bad!r}", result)
