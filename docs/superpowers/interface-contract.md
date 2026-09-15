# Interface contract

Written 2026-09-15, after chapter 1 landed. **This file is the coordination point for parallel
work.** Chapters 2 through 6 are being built by separate agents in separate worktrees, so the
module boundaries and signatures below are fixed before any of them start. An agent that needs
a signature not listed here adds it to its own module and reports the addition; it never changes
a signature another chapter already depends on.

Owner column is the chapter that creates the file. Nobody edits a file they do not own.

| File | Owner | Purpose |
| --- | --- | --- |
| `const.py` | ch1 (landed) | Every constant. Read-only for later chapters, additive changes allowed |
| `errors.py` | ch1 (landed) | The four typed errors. Do not add a fifth without saying why |
| `models.py` | ch1 (landed) | `VoiceInfo`, `VoiceCatalog`, `family_for_model` |
| `__init__.py` | ch1, revised ch3 | Entry setup, `DeepgramRuntimeData`. ch3 swaps the inline catalog fetch for `catalog.py` |
| `api.py` | ch2 | `DeepgramClient`: authenticated synthesis against both endpoints |
| `catalog.py` | ch3 | Unauthenticated catalog fetch, merge, and language to voice resolution |
| `config_flow.py` | ch1 stub, ch4 | API key step, voice picker, options flow |
| `tts.py` | ch1 stub, ch5, ch6 | The TTS entity. Batch in ch5, websocket in ch6 |
| `stream.py` | ch6 | The Flux websocket client, kept out of `tts.py` so the entity stays readable |

## Types already on disk

```python
# models.py
@dataclass(frozen=True, slots=True)
class VoiceInfo:
    voice_id: str                        # canonical_name, the model query parameter
    name: str                            # metadata.display_name
    family: str                          # FAMILY_FLUX | FAMILY_AURA
    languages: tuple[str, ...] = ()      # verbatim from the catalog, so en and en-US both appear
    accent: str | None = None
    age: str | None = None
    tags: tuple[str, ...] = ()
    sample_url: str | None = None

    @property
    def is_flux(self) -> bool: ...
    @property
    def base_languages(self) -> frozenset[str]: ...   # splits on "-", never "_"

@dataclass(frozen=True, slots=True)
class VoiceCatalog:
    voices: dict[str, VoiceInfo]
    def get(self, voice_id: str) -> VoiceInfo | None: ...

def family_for_model(model: str) -> str: ...

# errors.py
DeepgramError(HomeAssistantError)
DeepgramAuthError(DeepgramError)              # 401, 403
DeepgramConnectionError(DeepgramError)        # DNS, TCP, TLS, timeout, dropped socket
DeepgramRequestError(DeepgramError)           # other 4xx and 5xx. carries .status and .code
```

## Chapter 2: `api.py`

```python
class DeepgramClient:
    def __init__(self, session: ClientSession, api_key: str) -> None: ...

    async def async_verify_key(self) -> None:
        """Round trip a one-word synthesis. Raise DeepgramAuthError on a rejected key."""

    async def async_synthesize(
        self,
        text: str,
        *,
        model: str,
        encoding: str | None = None,
        container: str | None = None,
        sample_rate: int | None = None,
        speed: float | None = None,
    ) -> SynthesisResult: ...

@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio: bytes
    extension: str        # "mp3", "wav", ... what the API actually returned
    content_type: str
```

Rules for this chapter:

- Route on `family_for_model(model)`. `flux-*` to `URL_SPEAK_FLUX`, everything else to
  `URL_SPEAK_AURA`. One method, two URLs.
- `speed` is Flux only. Drop it silently for an Aura model rather than sending a parameter the
  v1 endpoint will reject.
- `sample_rate` must not be sent when `encoding` is `mp3`. The API rejects the combination.
- Reraise `DeepgramAuthError` and friends **before** any broad `except Exception`. A caller has
  to be able to tell an expired key from a dead network.
- `asyncio.timeout(TIMEOUT_SPEAK)`. Never `async_timeout`.
- Return what the API gave you. Do not decode or re-encode. HA transcodes in
  `_async_convert_audio` when the requested format differs, and doing it here is a full
  transcode per sentence on a Raspberry Pi for nothing.

## Chapter 3: `catalog.py`

```python
async def async_fetch_catalog(session: ClientSession) -> VoiceCatalog:
    """Fetch /v2/models and /v1/models, merge into one family-tagged catalog.

    Both endpoints are public and take no auth. Raise DeepgramConnectionError on failure so
    __init__ can turn it into ConfigEntryNotReady.
    """

def supported_languages(catalog: VoiceCatalog) -> list[str]:
    """Sorted base language codes across both families. Base codes only, never a mix."""

def voices_for_language(catalog: VoiceCatalog, language: str) -> list[VoiceInfo]:
    """Every voice that can speak `language`, Flux first. Accepts "en" or "en-US"."""

def resolve_voice(catalog: VoiceCatalog, language: str, preferred: str | None) -> VoiceInfo | None:
    """Pick the voice to use.

    `preferred` wins when it exists and can speak `language`. Otherwise DEFAULT_VOICE when the
    language is English. Otherwise the first Aura voice for that language, because every Flux
    voice is English and a Spanish pipeline must never resolve to Flux.
    """
```

Also in this chapter: replace `_async_fetch_catalogs` in `__init__.py` with a call to
`async_fetch_catalog`, and change `DeepgramRuntimeData.catalogs: dict` to
`catalog: VoiceCatalog`. That is the one cross-file edit chapter 3 owns.

## Chapter 4: `config_flow.py`

- `async_step_user`: API key, verified with `DeepgramClient.async_verify_key`. Map
  `DeepgramAuthError` to `invalid_auth`, `DeepgramConnectionError` to `cannot_connect`,
  anything else to `unknown`.
- `async_step_voice`: a `SelectSelector` of voices, grouped so Flux reads first, labels from
  `VoiceInfo.name` plus family and accent. Default `DEFAULT_VOICE`.
- Entry title is the chosen voice, for example `Deepgram Flux (Haley)`, so two entries are
  distinguishable in the UI.
- `unique_id` is the voice id, so the same voice cannot be added twice while a second voice
  still can. Not a constant, and `single_config_entry` stays absent.
- `OptionsFlow` with **no `__init__`**. `config_entry` is a read-only property the framework
  sets. Defining `__init__` to take or assign it breaks on 2025.12 and later.
- Options: voice, and speed only when the selected voice is Flux.

## Chapters 5 and 6: `tts.py`, `stream.py`

Chapter 5, batch:

- `supported_languages` from `catalog.supported_languages`, `default_language` is `"en"`.
- `async_get_supported_voices(language)` returns `list[Voice]` built from
  `voices_for_language`, using `VoiceInfo.name` for the label.
- `supported_options` is `[ATTR_VOICE, ATTR_AUDIO_OUTPUT, ATTR_PREFERRED_FORMAT, CONF_SPEED]`.
- `async_get_tts_audio` resolves the voice with `resolve_voice`, calls `async_synthesize`, and
  returns `(result.extension, result.audio)`.

Chapter 6, streaming. Do not start until chapter 5 runs on the real instance.

- `stream.py` opens `wss://api.deepgram.com/v2/speak?model=<flux voice>`, sends one `Speak` per
  chunk of `request.message_gen` **as each chunk arrives**, sends `Flush` when the generator is
  exhausted, and yields binary frames until `SpeechMetadata`.
- **The server places flush boundaries internally.** No sentence splitting, no buffering the
  message, no stitching fragments. A regex over the text means this paragraph was not read.
- Prepend a WAV header to the raw `linear16` and report `extension="wav"`.
- Fall back to the batch path when the socket fails or the voice is Aura. A dropped socket
  degrades; it does not raise.
- Overriding `async_stream_tts_audio` **is** the opt-in for streaming. There is no flag, and HA
  routes every Assist response down this path the moment the method exists. It has to work.

## Constraints on every chapter

- Python 3.14. `asyncio.timeout`, never `async_timeout`. No `pydub`, ever.
- Split language codes on `-`, never `_`.
- Every third-party import declared in manifest requirements, or use none.
  `scripts/manifest_check.py` enforces this.
- `uvx ruff@0.16.7 check .` and `format --check .` clean.
- Tests run with `.venv/bin/pytest`, which has HA 2026.9.2 and `pytest-homeassistant-custom-component` 0.13.365.
- Comments only where the why is not obvious. Docstrings in imperative mood; ruff enforces D401.
