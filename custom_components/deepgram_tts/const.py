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

# The socket emits raw linear16 with no container, so we ask for a rate we know rather than
# inferring one. The WAV header we prepend is wrong if this and the stream disagree, and wrong
# by a factor of two sounds like a chipmunk rather than like an error.
WS_ENCODING: Final = "linear16"
WS_SAMPLE_RATE: Final = 24000
WS_CHANNELS: Final = 1
WS_BITS_PER_SAMPLE: Final = 16

TIMEOUT_CATALOG: Final = 15
TIMEOUT_SPEAK: Final = 60
TIMEOUT_WS_CONNECT: Final = 10
TIMEOUT_WS_FRAME: Final = 30

# Added in chapter 2 for api.py.

# Both endpoints default to mp3 when no encoding is requested, so mp3 is also the fallback
# extension when nothing in the response or the request says otherwise.
ENCODING_MP3: Final = "mp3"
DEFAULT_EXTENSION: Final = ENCODING_MP3

# container=none means raw frames with no wrapper, so it is never a file extension.
CONTAINER_NONE: Final = "none"

# Response Content-Type to file extension. Deliberately short: an entry only belongs here when
# the container the header names is unambiguous, because the fallback (requested container,
# then requested encoding, then mp3) is always available and never wrong.
CONTENT_TYPE_EXTENSIONS: Final[dict[str, str]] = {
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
    "audio/aac": "aac",
    "audio/basic": "mulaw",
    "audio/l16": "pcm",
}

# Added in chapter 4 for config_flow.py.

# How each family is written where a person reads it: the entry title and the voice picker.
# Deepgram capitalizes both product names, and "aura" lower case in a title looks like a typo.
FAMILY_LABELS: Final[dict[str, str]] = {FAMILY_FLUX: "Flux", FAMILY_AURA: "Aura"}

# One word, synthesized and thrown away, to prove a key works during the config flow.
VERIFY_KEY_TEXT: Final = "Hello"

# A non-JSON error body goes into the exception message, so it has to be bounded.
ERROR_BODY_MAX_CHARS: Final = 200
