"""Constants for the Deepgram TTS integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "deepgram_tts"

# Flux voices are the primary path. Aura-2 exists to serve non-English pipelines.
FAMILY_FLUX: Final = "flux"
FAMILY_AURA: Final = "aura"

# Every Flux model id starts with this. It is the only routing signal the API gives us:
# posting an Aura model to /v2/speak is rejected with V1_MODEL_ON_V2_SPEAK_ENDPOINT.
FLUX_MODEL_PREFIX: Final = "flux-"

# American, adult, professional and empathetic per its catalog metadata, and the voice
# Deepgram's own quickstart uses, so it is the most recognizable default.
DEFAULT_VOICE: Final = "flux-haley-en"

API_HOST: Final = "api.deepgram.com"

URL_SPEAK_FLUX: Final = f"https://{API_HOST}/v2/speak"
URL_SPEAK_AURA: Final = f"https://{API_HOST}/v1/speak"
URL_SPEAK_FLUX_WS: Final = f"wss://{API_HOST}/v2/speak"

# Both catalogs are public and need no auth. /v2/models is Flux only, /v1/models is Aura only,
# so a merged voice list has to read both.
URL_MODELS_FLUX: Final = f"https://{API_HOST}/v2/models"
URL_MODELS_AURA: Final = f"https://{API_HOST}/v1/models"

CONF_VOICE: Final = "voice"
CONF_SPEED: Final = "speed"

DEFAULT_LANGUAGE: Final = "en"
DEFAULT_SPEED: Final = 1.0

# Flux only. /v2/speak validates 0.5 to 1.5 in 0.05 increments; Aura has no speed parameter.
SPEED_MIN: Final = 0.5
SPEED_MAX: Final = 1.5
SPEED_STEP: Final = 0.05

TIMEOUT_CATALOG: Final = 15
TIMEOUT_SPEAK: Final = 60
TIMEOUT_WS_CONNECT: Final = 10
TIMEOUT_WS_FRAME: Final = 30
