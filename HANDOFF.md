# Handoff: Deepgram Flux TTS for Home Assistant

**Self-contained.** Everything needed to start building is in this file. Nothing here depends on
another document, a web fetch, or a previous session. Written 2026-09-15, squashed from the session
that audited the existing community integration and decided to start clean.

If you are an agent picking this up: read the whole file before writing code. Sections 3 and 4 are
facts verified live, not recollection, and re-deriving them from the public docs will give you
thinner and in places wrong answers.

> **Read `docs/handoff-corrections.md` alongside this file.** Four claims here have been
> corrected since it was written, and one of them is a headline claim in section 2.1: the
> community integration's undeclared `async_timeout` import almost certainly **did** resolve on a
> real instance, because `ha-ffmpeg` requires `async-timeout` with no environment marker and the
> `tts` component depends on `ffmpeg`. The `pydub` half of that section stands and is the real
> cause. Section 3.4's `speed` range is also docs-sourced rather than probed: `/v2/speak` returns
> 401 for an out-of-range speed, so the range check runs after auth.
>
> This file is deliberately **not** edited in place. It records what the project believed on
> 2026-09-15, and knowing where the starting assumptions were wrong is half the value of a build
> log. Corrections are appended to that other file, never applied here.

---

## 1. What this project is

A Home Assistant custom integration that makes **Deepgram Flux TTS** the voice of a Home Assistant
voice assistant.

- Flux TTS is the primary path and the default voice.
- Aura-2 stays fully supported as a second family, because every Flux voice is English and Aura-2
  is the only way to serve a non-English Assist pipeline.
- Sam runs Home Assistant at home, so this gets tested on real hardware, not only in a dev
  container.

Domain: `deepgram_tts`. Distribution: HACS custom repository.

It sits alongside the other Flux TTS demos in this tree. `hn-radio-lab` is the batch long-form
demo. This is the real-time, in-the-house one.

---

## 2. Why we are not forking, and what came before

There is an existing community integration, `alceasan/ha-deepgram-tts`, last touched 2026-01-12.
It was forked to `samgutentag/ha-deepgram-tts` and audited in full at
`~/Developer/ha-deepgram-tts` (commit `ba59415`). **We are not building on it.** The fork stays on
the personal account as a credited reference and is not deleted.

Three reasons, in order of weight:

1. **Almost nothing survives.** Of roughly 850 lines of Python, the repair plan that came out of
   the audit deletes 206 outright and substantially rewrites another ~550. A generous estimate of
   surviving lines is ~180, about a fifth, and most of that is the config-flow shape.
2. **The history is worth more than the code.** The lab convention flips a shipped project into a
   public repo with history rewritten into build order so the commit log reads as a tutorial. A
   fresh build writes that history correctly the first time. A fork's log opens with someone else's
   initial commit plus five repair commits.
3. **A fork cannot be made private.** GitHub does not offer it. Making a parent private *detaches*
   its forks into a new network rather than converting them, forks stay public, and there is no
   documented self-serve way to leave a fork network. So "flip it private so the hub can live in
   it" was never available.

The fork was also carrying leftover `ludeeus/integration_blueprint` scaffolding: duplicate function
definitions, three dead exception classes, docstrings still describing the blueprint, and a mix of
English and Spanish comments.

### 2.1 What actually broke it, and why it matters to us

Worth knowing because both failures came from one line, and the second one is a trap anybody
writing an HA TTS entity can fall into.

`manifest.json` declared `"requirements": []` while the code imported two packages it did not own:

- **`async_timeout`** is not in HA core requirements, and aiohttp dropped it as a dependency at
  3.10 (HA ships 3.14.3). Nothing installs it, so the integration almost certainly did not load at
  all. Use `asyncio.timeout()`; it has been stdlib since 3.11.
- **`pydub`** is not an HA dependency either. Its optional-import guard left `AudioSegment = None`,
  and the streaming path then raised `RuntimeError("pydub is not available")` on every request.

The trap: because the fork overrode `async_stream_tts_audio`, HA's `async_supports_streaming_input()`
**auto-detected** streaming support and routed every Assist pipeline response down the broken path,
while direct `tts.speak` calls kept working. Overriding that method *is* the opt-in. There is no
flag. A half-built socket path goes live the moment the method exists.

### 2.2 Mistakes from that codebase, recorded so we do not repeat them

This is the transferable value of the audit. Each of these is a real defect found in the fork.

| Don't | Do |
| --- | --- |
| Split language codes on `_`. Deepgram uses hyphens (`en-US`, `es-419`), so `split("_")[0]` is a no-op and the language list ends up a mix of base and regional codes. It was wrong in 5 places. | `split("-")[0]` |
| Wrap the whole synthesize call in a broad `except Exception` that catches and rewraps your own auth exception, so callers cannot tell an expired key from a dead network. | Reraise your typed exceptions before the broad handler |
| Let a catalog fetch failure escape `async_setup_entry` as a raw aiohttp error, which marks the entry failed with no retry. | Raise `ConfigEntryNotReady` |
| Buffer the entire `request.message_gen` into one string before the first synthesis call, which deletes the whole point of streaming. | Forward each chunk as it arrives |
| Decode each returned MP3 and re-encode it. A full transcode per sentence on a Pi, for nothing. | Return what the API gave you; HA transcodes in `_async_convert_audio` when the requested format differs |
| Express single-instance with a hardcoded `async_set_unique_id("deepgram_tts")`. | Use the manifest's `single_config_entry` key, or allow multiple entries. We want multiple. |
| Define an `OptionsFlow.__init__` that takes or assigns `config_entry`. It is a read-only property set by the framework since 2025.12. | Omit the `__init__` entirely |
| Grow a buffer threshold as `2 ** count * 10`. By chunk 20 that is 10 MB. | Do not hand-roll sentence buffering at all; see section 3.5 |
| Reach through private attributes (`self._processor._client._models_cache`). | Pass the catalog in as a constructor argument |
| Ship a config flow with no `strings.json`, so both flows render bare step ids. | Write `strings.json` and `translations/en.json` in chapter 1 |
| Reference a devcontainer `Dockerfile` that is not in the repo. | Either add it or drop `.devcontainer.json` |

Also dead weight in that repo, listed so nobody ports it in: a `async_step_connection_test` that
nothing routes to, a `_strip_id3` helper never called, a `_trim_end_of_audio` made unreachable by
its own constant, a duplicated `_verify_response_or_raise`, and a `SYNTHESIS_DELAY_S = 0.15` sleep
before every call.

---

## 3. Verified facts: the Deepgram API

Confirmed live on 2026-09-15 by probing `api.deepgram.com`, which returns real parameter validation
**before** it checks auth. That is why a dummy key was enough to enumerate schemas. Do not replace
any of this with what the docs say; the docs are thinner.

### 3.1 Endpoints

| Purpose | Endpoint |
| --- | --- |
| Flux batch | `POST https://api.deepgram.com/v2/speak` |
| Flux streaming | `wss://api.deepgram.com/v2/speak` |
| Aura batch | `POST https://api.deepgram.com/v1/speak` |
| Flux voice catalog | `GET https://api.deepgram.com/v2/models` (public, no auth, HTTP 200) |
| Aura voice catalog | `GET https://api.deepgram.com/v1/models` (public, no auth, HTTP 200) |

### 3.2 The two families do not mix

Posting an Aura model to `/v2/speak` returns HTTP 400:

```json
{"err_code":"V1_MODEL_ON_V2_SPEAK_ENDPOINT",
 "err_msg":"Only flux models are supported on the `/v2/speak` endpoint. Please use the `/v1/speak` endpoint for Aura text-to-speech requests."}
```

That check runs before auth. So the client routes on the model id: `flux-*` to v2, everything else
to v1. One synthesize signature, two URLs.

### 3.3 Voice catalogs

- **`/v2/models`** returns exactly **36** voices, all `architecture: "flux-tts"`, all English.
  Languages per voice are `["en", "en-US"]` or a regional variant; the catalog's language set is
  `en, en-AU, en-GB, en-IE, en-IN, en-PH, en-SG, en-US`. The full id list:

  ```
  flux-alexis-en    flux-bree-en      flux-brittany-en  flux-brooke-en
  flux-bruce-en     flux-cliff-en     flux-cole-en      flux-colin-en
  flux-conor-en     flux-donovan-en   flux-drew-en      flux-elise-en
  flux-gemma-en     flux-haley-en     flux-hannah-en    flux-heather-en
  flux-jack-en      flux-kai-en       flux-kelsey-en    flux-kit-en
  flux-maeve-en     flux-marcelo-en   flux-marcus-en    flux-meena-en
  flux-meghan-en    flux-miles-en     flux-naveen-en    flux-paige-en
  flux-priya-en     flux-rufus-en     flux-sean-en      flux-sharon-en
  flux-sienna-en    flux-tanner-en    flux-wade-en      flux-wes-en
  ```

- **`/v1/models`** returns **102** TTS models: 90 `aura-2` plus 12 legacy `aura`. Languages:
  `de, de-DE, en, en-AU, en-GB, en-IE, en-PH, en-US, es, es-419, es-AR, es-CO, es-ES, es-MX, fr,
  fr-FR, it, it-IT, ja, ja-JP, nl, nl-NL`. **Zero Flux entries**, which is why the fork's dynamic
  voice discovery could never see Flux at all.

- Both payloads are `{"stt": [...], "tts": [...], "languages": {...}}`. Each `tts` entry:

  ```json
  {
    "name": "alexis",
    "canonical_name": "flux-alexis-en",
    "architecture": "flux-tts",
    "languages": ["en", "en-US"],
    "version": "2026-08-12.0",
    "uuid": "36f312ab-d06a-4c1c-9071-ba18bebb29e9",
    "metadata": {
      "accent": "American", "age": "Adult", "display_name": "Alexis",
      "image": "https://cdn.sanity.io/...", "sample": "https://cdn.sanity.io/....wav",
      "tags": ["feminine","clear","professional","calm","caring","empathetic"],
      "use_cases": ["Customer Service","IVR","Financial Services"]
    }
  }
  ```

  Use `metadata.display_name` for anything a person reads. `name` is the bare lowercase given name.
  `metadata.sample` is a playable WAV, which is useful for a voice picker later.

### 3.4 `/v2/speak` batch

```bash
curl "https://api.deepgram.com/v2/speak?model=flux-haley-en" \
  -H "Authorization: Token $DEEPGRAM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Your appointment is confirmed for 3pm tomorrow."}' \
  --output audio.mp3
```

Query parameters, enumerated by sending deliberately invalid values and reading the rejections:

| Param | Values |
| --- | --- |
| `model` | required, `flux-*` only |
| `encoding` | `linear16`, `mulaw`, `alaw`, `mp3`, `opus`, `flac`, `aac`. Default `mp3` |
| `container` | `wav`, `ogg`, `none` |
| `sample_rate` | rejected when `encoding=mp3` ("not applicable") |
| `speed` | 0.5 to 1.5, 0.05 increments |
| `bit_rate` | accepted |
| `mip_opt_out` | accepted |
| `callback` | accepted |

Unknown params are rejected outright with `INVALID_QUERY_PARAMETER`. Compressed and containerized
encodings are batch-only; the socket emits raw `linear16`, `mulaw`, or `alaw`.

`/v1/speak` for Aura takes the same JSON body shape. Its documented defaults are
`model=aura-asteria-en`, `encoding=mp3`, `container=wav`, `sample_rate=24000`, `bit_rate=48000`.

### 3.5 Flux TTS websocket

```
wss://api.deepgram.com/v2/speak?model=flux-haley-en
Authorization: Token $DEEPGRAM_API_KEY
```

Client messages:

```json
{"type":"Speak","text":"Sure, I can help you cancel that."}
{"type":"Flush"}
{"type":"Interrupt","playback_offset":{"type":"time_ms","value":2340}}
{"type":"Configure","speed":1.15}
{"type":"Close"}
```

Server messages, with their fields:

| Message | Fields |
| --- | --- |
| `Connected` | `request_id`, `model_name`, `model_version`, `model_uuids` |
| `SpeechStarted` | `speech_id` |
| `SpeechMetadata` | `speech_id`, `audio_duration_ms`, `input_character_count`, `billable_character_count`, `controls_applied` |
| `SpeechInterrupted` | `audio_played_ms`, `text_spoken`, `text_remaining`, `metadata` |
| `Flushed` | `speech_id` |
| `SessionMetadata` | `total_audio_duration_ms`, `total_input_character_count`, `total_billable_character_count` |
| `ConfigureSuccess` | `applied` |
| `ConfigureFailure` | `code`, `field`, `value`, `description` |
| `Warning` / `Error` | `code`, `description` |

Every audio frame for a turn arrives **between `SpeechStarted` and `SpeechMetadata`**, as binary
frames interleaved with JSON text frames. `SpeechMetadata` means all of that turn's audio has been
sent.

**The single most important fact in this document:** the server places flush boundaries internally.
Stream LLM tokens straight in. That means no sentence splitting, no per-sentence round trips, and
no audio fragment stitching on our side. It is why the fork's 206-line `stream_processor.py` has no
equivalent here.

Pricing, for reference in any write-up: $0.045 per 1,000 characters.

---

## 4. Verified facts: Home Assistant

From `home-assistant/core` @ `dev`, read 2026-09-15.

### 4.1 Environment

- Version `2026.10.0.dev0`, so current stable is 2026.9.x.
- `requires-python = ">=3.14.2"`.
- `aiohttp==3.14.3`. `async_timeout` is **not** in core requirements.
- `audioop-lts==0.2.2` is in core. `python-slugify` is available. `pydub` is not, and we do not
  need it.

### 4.2 The TTS entity contract

```python
# homeassistant/components/tts/entity.py
@dataclass
class TTSAudioRequest:
    language: str
    options: dict[str, Any]
    message_gen: AsyncGenerator[str]

@dataclass
class TTSAudioResponse:
    extension: str
    data_gen: AsyncGenerator[bytes]

# homeassistant/components/tts/models.py
@dataclass(frozen=True)
class Voice:
    voice_id: str
    name: str
```

Methods and properties:

```python
async def async_get_tts_audio(self, message, language, options) -> TtsAudioType
async def async_stream_tts_audio(self, request: TTSAudioRequest) -> TTSAudioResponse
@callback
def async_get_supported_voices(self, language: str) -> list[Voice] | None
@cached_property
def supported_options(self) -> list[str] | None
@cached_property
def default_options(self) -> Mapping[str, Any] | None
def async_supports_streaming_input(self) -> bool   # do not override
```

`async_supports_streaming_input()` auto-detects by comparing
`self.__class__.async_stream_tts_audio` against the base method. See section 2.1.

### 4.3 Option constants and conversion

From `homeassistant/components/tts/__init__.py`:

- `ATTR_VOICE = "voice"`
- `ATTR_PREFERRED_FORMAT = "preferred_format"`
- `ATTR_PREFERRED_SAMPLE_RATE = "preferred_sample_rate"`
- `_DEFAULT_FORMAT = "mp3"`

HA converts audio itself in `_async_convert_audio` whenever the final requested format differs from
what the entity returned, or when a sample rate, channel count, byte width, or bitrate was
requested. So returning WAV and letting HA transcode is correct and free. Doing our own transcode
is waste.

### 4.4 Manifest notes

- `single_config_entry: true` is the sanctioned way to express single-instance. We want a Flux
  entity and an Aura entity side by side, so we do **not** set it, and we do not fake it with a
  constant `unique_id` either.
- `iot_class`: closest core analog is `elevenlabs`, which uses `cloud_polling`.
- `integration_type: "service"`, `config_flow: true`.
- Declare every third-party import in `requirements`. If the answer is "none," that should be true
  because we only use stdlib plus what HA already ships.

---

## 5. Settled design decisions

Do not relitigate these. They came out of a full audit plus live API probing.

1. **Route by model prefix.** `flux-*` to `/v2/speak`, everything else to `/v1/speak`.
2. **Merge both catalogs into one voice list**, keyed by `canonical_name`, labeled from
   `metadata.display_name`, each entry tagged with its family so the UI can group them.
3. **Default voice is `flux-haley-en`.** American, young adult, professional and empathetic per its
   metadata, and the voice Deepgram's own quickstart uses, so it is the most recognizable default.
4. **Non-English never resolves to Flux.** `supported_languages` is the union of both families.
   Voice resolution for es, de, fr, nl, it, or ja must return an Aura-2 voice.
5. **Streaming is the websocket, with a batch fallback.** Fall back to `/v2/speak` batch when the
   socket fails or when the selected voice is Aura, so a dropped connection degrades instead of
   erroring.
6. **WAV out of the socket.** The socket gives raw `linear16` with no container, so prepend a WAV
   header and report `extension="wav"`. Advertise `preferred_format` in `supported_options` and let
   HA handle anything else.
7. **Speed is Flux-only.** Hide or ignore the option when an Aura voice is selected.
8. **Barge-in is out of scope.** `SpeechInterrupted.text_spoken` is the right primitive, but HA's
   TTS entity API has no barge-in hook today. Note it; do not build it.

### 5.1 One engineering note on voice defaults

`flux-marcus-en` and `flux-brittany-en` drift in pitch and volume between calls, sometimes emit an
audible musical note before a greeting, and can click at clip starts. A home assistant makes many
short separate calls, which is exactly where that drift is most audible, so neither is a good
shipped default. Both are cleared for use and belong in the picker. This is engineering advice
about defaults, not a permission question, and the permission question is settled.

---

## 6. Build order

Seven chapters, written as build order on purpose so the eventual public history reads as a
tutorial with no rewrite needed. One commit per chapter, or a small tight series within a chapter.

| # | Chapter | Lands |
| --- | --- | --- |
| 1 | Scaffold | `manifest.json`, `hacs.json`, `const.py`, `strings.json`, `translations/en.json`, hassfest and HACS CI, ruff config, `tests/` skeleton |
| 2 | API client | Two endpoints, JSON bodies, typed errors, `asyncio.timeout`. First authenticated round trip |
| 3 | Voice catalog | Fetch and merge `/v1/models` and `/v2/models` into one family-tagged list |
| 4 | Config flow | API key step, voice picker, options flow, multiple entries allowed |
| 5 | TTS entity, batch | Flux default, language routing, `async_get_tts_audio` against `/v2/speak` |
| 6 | TTS entity, streaming | Websocket client, `async_stream_tts_audio`, WAV header, batch fallback |
| 7 | Harden | Real-hardware notes, README, CHANGELOG, first tag |

Chapter 6 is the only one with real design risk. Everything before it is mechanical.

**Get chapter 5 onto the real Home Assistant instance before starting 6.** A working batch path on
real hardware is what makes the streaming work verifiable rather than theoretical.

### 6.1 Verification per chapter

- **2:** one authenticated round trip against both `/v1/speak` and `/v2/speak`, audio plays.
- **4:** hassfest and HACS validation pass, config flow shows real labels, the language dropdown
  shows base codes only and not a mix of `en` and `en-US`.
- **5:** `flux-haley-en` is the default on a fresh install, a Spanish pipeline resolves an Aura
  voice, `tts.speak` produces audio on the real instance.
- **6:** the first audio frame arrives before the LLM has finished its sentence, and killing the
  socket mid-turn degrades to batch instead of raising.

---

## 7. Still unverified

Carry these forward. They are open.

1. **No Deepgram API key was available in the audit session.** Nothing past the auth check has been
   exercised. Every endpoint fact in section 3 comes from unauthenticated probes plus docs. First
   real task in chapter 2 is an authenticated round trip against both endpoints.
2. **First-frame latency over the socket is unmeasured.** Deepgram's marketing claims audio starts
   in as low as 80ms. Treat that as a claim to test, not a fact to repeat, and measure it on the
   target hardware rather than on a laptop.
3. **Whether `/v1/speak` rejects a `text/plain` body** is unknown, because auth is validated before
   the body and a dummy key always returns 401. Only affects the Aura path.

---

## 8. Environment and conventions

Facts about this machine that are easy to get wrong and expensive to get wrong.

### 8.1 Git identity comes from the directory

`~/.gitconfig` uses `includeIf` blocks:

| Tree | Identity |
| --- | --- |
| `~/LABS/`, `~/DEEPGRAM/`, `~/EVENTS/` | work (`samgutentag-deepgram`) |
| `~/Developer/`, `~/TINKER/` | personal (`samgutentag`) |

**The global default is the work account.** So anything outside those trees silently gets work
identity. Never set a repo-local `user.email`. Verified for this repo: commits author as
`307399679+samgutentag-deepgram@users.noreply.github.com`, with no local override.

If you create git worktrees, keep them inside the same tree as the repo.

### 8.2 The lab convention

Every repo in `~/LABS` is private and carries the `-lab` suffix. If it ships, it is snapshotted
**once** into a separate public repo named without the suffix. The flip is one way and terminal:

- History is rewritten into build order first. Our chapter structure is meant to make that a no-op.
- `.hub/` and `advocacy/` are stripped from **every** commit, not just the tip. A `.gitignore` line
  does not do this.
- After the flip the public repo is the repo of record. PRs there are applied by hand here.
- `hub.yml` gets a `public_repo:` key once the flip happens.

Flip target for this project: `samgutentag-deepgram/ha-deepgram-tts`. No collision with the personal
fork of the same name; different account.

### 8.3 Tooling drift to fix

`~/.claude/CLAUDE.md` states that the active `gh` account is the work one and tells you to reach for
the personal token. That is backwards as of 2026-09-15: `gh auth status` shows `samgutentag` active
and `samgutentag-deepgram` inactive. Anything touching this repo's remote needs the **work** token,
for example via `gh auth token --user samgutentag-deepgram` through a one-off credential helper.

### 8.4 Document format

- Prose a person reads becomes print-ready HTML from
  `~/Developer/gutils/templates/print-ready-html-doc.html`, copying its `<style>`, `#theme-toggle`,
  and theme `<script>` verbatim. Open with `open -a "Google Chrome" <file>`, once, then say
  "refresh the tab."
- Notes an agent reads stay markdown. This file, `STARTER-PROMPT.md`, and `.hub/ledger.md` are
  markdown for that reason.
- Specs and plans go to `docs/superpowers/*.md` as canonical, with a derived HTML review copy beside
  them that is gitignored and never edited directly.
- No em dashes in any of it.
- There is no markdown renderer installed on this machine (no `markdown`, `mistune`, or `pandoc`),
  so rendering a plan to HTML needs a small local script.

### 8.5 Sequencing for hub and advocacy

1. `/project-hub init` writes `.hub/` (`index.html`, `hub.yml`, `ledger.md`, `assets/`) and wires
   the repo to Asana. The Asana call is outward-facing, so it needs a go-ahead. `init` is
   idempotent and never clobbers authored content.
2. `.hub/ledger.md` is append-only and records only what a repo scan cannot recover: the choice and
   what it cost, the symptom before anyone knew the cause, the thing tried and reverted. Capture
   generously; the harvest step trims.
3. Progress and status live in Asana, never in `.hub/`. Never add a `status:` or `progress:` key to
   `hub.yml`.
4. `/advocacy-intake` freezes the claim and creates the Asana entry. `advocacy-cycle` refuses to
   run without both. **Do not start intake before chapter 5 is on real hardware**; there is nothing
   honest to claim yet.

---

## 9. Optional reference material

In `docs/`, kept for depth but not required by anything above:

- `state-of-the-fork-2026-09-15.html` holds the full audit of the community integration, with
  file-and-line findings.
- `flux-first-rewrite-plan.md` is the superseded 16-commit repair plan for the fork. Its code
  review section is the most detailed record of what that codebase does.
- `eli5-flux-first-plan.html` is eleven diagrams covering the same ground. Raw material for a
  later write-up.
