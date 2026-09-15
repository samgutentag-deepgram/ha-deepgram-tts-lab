"""Config flow for Deepgram TTS.

Chapter 4. Three pieces: a key step that verifies the key before an entry exists, a voice step
that turns the merged catalog into one picker, and an options flow that re-offers the voice plus
a Flux only speed.

The unique_id is the voice id, never a constant. That is what makes adding the same voice twice
abort while adding a second, different voice succeeds, and it is why `single_config_entry` is
absent from the manifest.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .api import DeepgramClient
from .catalog import async_fetch_catalog
from .const import (
    CONF_SPEED,
    CONF_VOICE,
    DEFAULT_LANGUAGE,
    DEFAULT_SPEED,
    DEFAULT_VOICE,
    DOMAIN,
    FAMILY_FLUX,
    FAMILY_LABELS,
    SPEED_MAX,
    SPEED_MIN,
    SPEED_STEP,
)
from .errors import DeepgramAuthError, DeepgramConnectionError
from .models import VoiceCatalog, VoiceInfo, family_for_model

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


def _family_label(family: str) -> str:
    """Return the readable name for a family."""
    return FAMILY_LABELS.get(family, family.title())


def voice_label(voice: VoiceInfo) -> str:
    """Build the picker label for one voice.

    The label ends in the voice id because the name alone is not unique. 61 of the 102 live Aura
    entries report `display_name` as null and fall back to a title-cased bare name, so the
    legacy `aura-asteria-en` and the current `aura-2-asteria-en` both read as "Asteria" with the
    same family and the same accent. The id also happens to be the model string the integration
    sends, which is the thing someone comparing this against Deepgram's docs wants to see.

    Language codes are only appended for a voice that cannot speak English, because 89 of the
    138 voices are English and repeating "en" on all of them buys nothing.
    """
    parts = [_family_label(voice.family)]
    if voice.accent:
        parts.append(voice.accent)
    if DEFAULT_LANGUAGE not in voice.base_languages:
        parts.append(", ".join(sorted(voice.base_languages)))
    return f"{voice.name} ({', '.join(parts)}) [{voice.voice_id}]"


def entry_title(voice_id: str, voice: VoiceInfo | None) -> str:
    """Build the entry title, for example Deepgram Flux (Haley)."""
    family = voice.family if voice is not None else family_for_model(voice_id)
    name = voice.name if voice is not None else voice_id
    return f"Deepgram {_family_label(family)} ({name})"


def _sort_key(voice: VoiceInfo) -> tuple[bool, bool, str, str, str]:
    """Order the picker: Flux first, then English Aura, then the other languages by code."""
    languages = sorted(voice.base_languages)
    return (
        not voice.is_flux,
        DEFAULT_LANGUAGE not in voice.base_languages,
        languages[0] if languages else "",
        voice.name.casefold(),
        voice.voice_id,
    )


def _voice_schema(catalog: VoiceCatalog, default: str) -> vol.Schema:
    """Build the voice field over the whole merged catalog."""
    options = [
        SelectOptionDict(value=voice.voice_id, label=voice_label(voice))
        for voice in sorted(catalog.voices.values(), key=_sort_key)
    ]
    return vol.Schema(
        {
            vol.Required(CONF_VOICE, default=default): SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=False,
                    # Sorting in the frontend would alphabetize the labels and throw away the
                    # Flux-first order this integration is built around.
                    sort=False,
                )
            )
        }
    )


def _default_voice(catalog: VoiceCatalog, preferred: str | None = None) -> str:
    """Return the voice to preselect, preferring one the catalog actually has."""
    for candidate in (preferred, DEFAULT_VOICE):
        if candidate and candidate in catalog.voices:
            return candidate
    ordered = sorted(catalog.voices.values(), key=_sort_key)
    return ordered[0].voice_id if ordered else DEFAULT_VOICE


class DeepgramConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Deepgram TTS.

    Two steps rather than one, because the voice list cannot be built before a key has been
    accepted and the catalog fetched.
    """

    VERSION = 1

    _api_key: str
    _catalog: VoiceCatalog

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the API key, verify it, and load the voice catalog."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            session = async_get_clientsession(self.hass)
            try:
                await DeepgramClient(session, api_key).async_verify_key()
                catalog = await async_fetch_catalog(session)
            except DeepgramAuthError:
                errors["base"] = "invalid_auth"
            except DeepgramConnectionError:
                # A failed catalog fetch lands here too. It is transient, so the form comes
                # back with an error instead of aborting the flow.
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error setting up Deepgram TTS")
                errors["base"] = "unknown"
            else:
                self._api_key = api_key
                self._catalog = catalog
                return await self.async_step_voice()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_voice(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the voice this entry speaks with."""
        if user_input is not None:
            voice_id = user_input[CONF_VOICE]
            # The voice id is the unique_id, so this is what refuses a duplicate voice while
            # still allowing a second entry for a different one.
            await self.async_set_unique_id(voice_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=entry_title(voice_id, self._catalog.get(voice_id)),
                data={CONF_API_KEY: self._api_key},
                options={CONF_VOICE: voice_id},
            )

        return self.async_show_form(
            step_id="voice",
            data_schema=_voice_schema(self._catalog, _default_voice(self._catalog)),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DeepgramOptionsFlow:
        """Return the options flow for an existing entry."""
        return DeepgramOptionsFlow()


class DeepgramOptionsFlow(OptionsFlow):
    """Change the voice, and the speed when that voice is a Flux voice.

    There is no `__init__` on purpose. `config_entry` is a read-only property the framework
    sets, and a constructor that takes or assigns it raises on Home Assistant 2025.12 and later.
    That was a real defect in the codebase this project replaces.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options form, or save what came back from it."""
        options = self.config_entry.options
        current_voice = options.get(CONF_VOICE, DEFAULT_VOICE)

        if user_input is not None:
            voice_id = user_input[CONF_VOICE]
            saved: dict[str, Any] = {CONF_VOICE: voice_id}
            # Speed is dropped rather than carried across a switch to Aura, because /v1/speak
            # has no speed parameter and a stored value nothing reads is a lie.
            if family_for_model(voice_id) == FAMILY_FLUX and CONF_SPEED in user_input:
                saved[CONF_SPEED] = user_input[CONF_SPEED]
            # Saving fires the update listener __init__ already registered, which reloads.
            return self.async_create_entry(data=saved)

        catalog = await self._async_catalog()
        if catalog is None:
            return self.async_abort(reason="cannot_connect")

        schema = _voice_schema(catalog, _default_voice(catalog, current_voice))
        if family_for_model(current_voice) == FAMILY_FLUX:
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_SPEED, default=options.get(CONF_SPEED, DEFAULT_SPEED)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=SPEED_MIN,
                            max=SPEED_MAX,
                            step=SPEED_STEP,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    )
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def _async_catalog(self) -> VoiceCatalog | None:
        """Return the catalog the entry already holds, or fetch one.

        A loaded entry has it in `runtime_data`. An entry in SETUP_RETRY does not, and its
        options are still reachable from the UI, so fall back to a fetch rather than render an
        empty picker that would silently drop the configured voice.
        """
        runtime = getattr(self.config_entry, "runtime_data", None)
        catalog = getattr(runtime, "catalog", None)
        if isinstance(catalog, VoiceCatalog):
            return catalog

        try:
            return await async_fetch_catalog(async_get_clientsession(self.hass))
        except DeepgramConnectionError as err:
            _LOGGER.warning("Could not load the Deepgram voice list: %s", err)
            return None
