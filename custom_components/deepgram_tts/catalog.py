"""The voice catalog: fetch both public model lists, merge them, resolve a language to a voice.

Deepgram splits its voices across two endpoints that do not overlap. `/v2/models` is Flux only
and `/v1/models` is Aura only, so a single voice list has to read both and tag each entry with
its family. Neither endpoint takes an API key, so this module never sees one.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    DEFAULT_LANGUAGE,
    DEFAULT_VOICE,
    TIMEOUT_CATALOG,
    URL_MODELS_AURA,
    URL_MODELS_FLUX,
)
from .errors import DeepgramConnectionError
from .models import VoiceCatalog, VoiceInfo, family_for_model

_LOGGER = logging.getLogger(__name__)


async def async_fetch_catalog(session: ClientSession) -> VoiceCatalog:
    """Fetch /v2/models and /v1/models, merge into one family-tagged catalog.

    Both endpoints are public and take no auth. Raise DeepgramConnectionError on failure so
    __init__ can turn it into ConfigEntryNotReady.
    """
    try:
        async with asyncio.timeout(TIMEOUT_CATALOG):
            flux_payload, aura_payload = await asyncio.gather(
                _async_get_catalog(session, URL_MODELS_FLUX),
                _async_get_catalog(session, URL_MODELS_AURA),
            )
    except (ClientError, TimeoutError) as err:
        raise DeepgramConnectionError(
            f"Could not read the Deepgram voice catalogs at {URL_MODELS_FLUX} "
            f"and {URL_MODELS_AURA}: {err}"
        ) from err

    voices: dict[str, VoiceInfo] = {}
    # Flux first, so a collision resolves in its favor and the dict reads Flux before Aura.
    for source, payload in ((URL_MODELS_FLUX, flux_payload), (URL_MODELS_AURA, aura_payload)):
        for voice in _voices_from_payload(payload, source=source):
            existing = voices.get(voice.voice_id)
            if existing is not None:
                # /v2/models has zero Aura entries and /v1/models has zero Flux entries, so a
                # shared id means one of the endpoints changed shape. Keep Flux and say so.
                _LOGGER.warning(
                    "Voice id %s appears in both catalogs; keeping the %s entry",
                    voice.voice_id,
                    existing.family,
                )
                continue
            voices[voice.voice_id] = voice

    if not voices:
        _LOGGER.warning("Both Deepgram catalogs parsed to zero voices")

    _LOGGER.debug("Merged voice catalog holds %d voices", len(voices))
    return VoiceCatalog(voices=voices)


def supported_languages(catalog: VoiceCatalog) -> list[str]:
    """Return the sorted base language codes across both families.

    Base codes only, never a mix. Deepgram reports both `en` and `en-US` on the same voice, and
    handing Home Assistant both makes one language look like two.
    """
    codes: set[str] = set()
    for voice in catalog.voices.values():
        codes |= voice.base_languages
    return sorted(codes)


def voices_for_language(catalog: VoiceCatalog, language: str) -> list[VoiceInfo]:
    """Return every voice that can speak `language`, Flux first. Accept "en" or "en-US"."""
    base = _base_code(language)
    matches = [voice for voice in catalog.voices.values() if base in voice.base_languages]
    # Sorted, not catalog order, so the picker and the voice list are stable across restarts.
    return sorted(matches, key=lambda voice: (not voice.is_flux, voice.name.casefold()))


def resolve_voice(catalog: VoiceCatalog, language: str, preferred: str | None) -> VoiceInfo | None:
    """Pick the voice to use.

    `preferred` wins when it exists and can speak `language`. Otherwise DEFAULT_VOICE when the
    language is English. Otherwise the first Aura voice for that language, because every Flux
    voice is English and a Spanish pipeline must never resolve to Flux.
    """
    base = _base_code(language)
    candidates = voices_for_language(catalog, language)

    if preferred:
        voice = catalog.get(preferred)
        if voice is None:
            _LOGGER.warning("Preferred voice %s is not in the catalog", preferred)
        elif base not in voice.base_languages:
            _LOGGER.debug("Preferred voice %s cannot speak %s", preferred, language)
        else:
            return voice

    if base == DEFAULT_LANGUAGE:
        default = catalog.get(DEFAULT_VOICE)
        if default is not None and base in default.base_languages:
            return default

    for voice in candidates:
        if not voice.is_flux:
            return voice

    # Only reachable for English, and only when the catalog has no Aura English voice at all.
    # Guarded on the base code rather than on the voice, so settled decision 4 holds even if
    # Deepgram ever tags a Flux voice with a language it cannot actually speak.
    if base == DEFAULT_LANGUAGE and candidates:
        return candidates[0]

    _LOGGER.warning("No voice in the catalog can speak %s", language)
    return None


def _base_code(language: str) -> str:
    """Reduce a language code to its base.

    Deepgram uses hyphens (`en-US`, `es-419`), so the split is on a hyphen. Splitting on an
    underscore is a no-op that leaves `en` and `en-US` looking like different languages, which
    is the exact bug the codebase this replaces had in five places.
    """
    return language.split("-")[0].lower()


async def _async_get_catalog(session: ClientSession, url: str) -> Any:
    """Fetch one public catalog. No Authorization header: these endpoints take no auth."""
    response = await session.get(url)
    response.raise_for_status()
    return await response.json()


def _voices_from_payload(payload: Any, *, source: str) -> list[VoiceInfo]:
    """Build a voice per usable `tts` entry in one catalog payload.

    The payload is `{"stt": [...], "tts": [...], "languages": {...}}` and only `tts` matters
    here. One malformed entry is skipped rather than losing the whole catalog with it.
    """
    entries = payload.get("tts") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        _LOGGER.warning("%s returned no tts list, so it contributed no voices", source)
        return []

    voices: list[VoiceInfo] = []
    for entry in entries:
        voice = _voice_from_entry(entry, source=source)
        if voice is not None:
            voices.append(voice)
    return voices


def _voice_from_entry(entry: Any, *, source: str) -> VoiceInfo | None:
    """Normalize one `tts` entry, or return None when it is unusable."""
    if not isinstance(entry, dict):
        _LOGGER.warning("Skipping a tts entry from %s that is not an object", source)
        return None

    voice_id = entry.get("canonical_name")
    if not isinstance(voice_id, str) or not voice_id:
        _LOGGER.warning(
            "Skipping a tts entry from %s with no canonical_name (name=%r)",
            source,
            entry.get("name"),
        )
        return None

    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return VoiceInfo(
        voice_id=voice_id,
        name=_display_name(voice_id, entry, metadata),
        family=family_for_model(voice_id),
        languages=_string_tuple(entry.get("languages")),
        accent=_optional_string(metadata.get("accent")),
        age=_optional_string(metadata.get("age")),
        tags=_string_tuple(metadata.get("tags")),
        sample_url=_optional_string(metadata.get("sample")),
    )


def _display_name(voice_id: str, entry: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Return the label a person should see.

    `metadata.display_name` is the field to show, but 61 of the 102 live Aura entries carry it
    as null, so the title-cased `name` fallback is load-bearing rather than defensive.
    """
    display_name = _optional_string(metadata.get("display_name"))
    if display_name:
        return display_name
    bare_name = _optional_string(entry.get("name"))
    return bare_name.title() if bare_name else voice_id


def _optional_string(value: Any) -> str | None:
    """Return a non-empty stripped string, or None for anything else."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    """Return the string items of a list, dropping anything that is not one."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)
