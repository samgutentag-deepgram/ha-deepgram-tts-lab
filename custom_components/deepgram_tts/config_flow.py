"""Config flow for Deepgram TTS.

Chapter 1 has the minimum a manifest with config_flow true is allowed to ship: one API key
step, no validation. Chapter 4 adds key verification, the voice picker, and the options flow.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
import voluptuous as vol

from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class DeepgramConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Deepgram TTS.

    single_config_entry is deliberately absent from the manifest and no constant unique_id is
    set here, because a Flux entity and an Aura entity side by side is a supported setup.
    """

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the API key."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        return self.async_create_entry(title="Deepgram TTS", data=user_input)
