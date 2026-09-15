"""Shared value types.

These are the only types passed between the client, the catalog, the config flow, and the
entity, which is what keeps any of them from reaching into another's internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import FAMILY_AURA, FAMILY_FLUX, FLUX_MODEL_PREFIX


@dataclass(frozen=True, slots=True)
class VoiceInfo:
    """One synthesis voice, normalized across the two catalog shapes."""

    voice_id: str
    """Deepgram's canonical_name, for example flux-haley-en. This is the model query parameter."""

    name: str
    """metadata.display_name. The only field a person should ever be shown."""

    family: str
    """FAMILY_FLUX or FAMILY_AURA."""

    languages: tuple[str, ...] = ()
    """Languages exactly as the catalog reports them, so both en and en-US may appear."""

    accent: str | None = None
    age: str | None = None
    tags: tuple[str, ...] = ()
    sample_url: str | None = None

    @property
    def is_flux(self) -> bool:
        """Whether this voice routes to the v2 endpoints."""
        return self.family == FAMILY_FLUX

    @property
    def base_languages(self) -> frozenset[str]:
        """Base language codes only.

        Deepgram uses hyphens (en-US, es-419), so the split is on a hyphen. Splitting on an
        underscore is a no-op and leaves a language list that mixes en with en-US.
        """
        return frozenset(lang.split("-")[0] for lang in self.languages)


@dataclass(frozen=True, slots=True)
class VoiceCatalog:
    """The merged Flux and Aura catalogs, keyed by voice id."""

    voices: dict[str, VoiceInfo] = field(default_factory=dict)

    def get(self, voice_id: str) -> VoiceInfo | None:
        """Look up one voice, or None if it is not in either catalog."""
        return self.voices.get(voice_id)


def family_for_model(model: str) -> str:
    """Return which family a model id belongs to, from its prefix alone."""
    return FAMILY_FLUX if model.startswith(FLUX_MODEL_PREFIX) else FAMILY_AURA
