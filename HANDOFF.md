# Handoff: Deepgram Flux TTS for Home Assistant

Written 2026-09-15. Everything a cold agent needs to start building here, carried over from the
session that audited the existing community integration and decided not to build on it.

Read this first, then `docs/`.

---

## What this project is

A Home Assistant custom integration that makes Deepgram Flux TTS the voice of a Home Assistant
voice assistant. Flux TTS is the primary path and the default voice. Aura-2 stays supported as a
second family because every Flux voice is English and Aura-2 is the only way to serve a
non-English Assist pipeline.

Sam runs Home Assistant at home, so this gets tested on real hardware rather than only in a dev
container.

It sits alongside the other Flux TTS demos in this tree. `hn-radio-lab` is the batch long-form
demo; this is the real-time, interrupt-driven, in-the-house one.

## Where it came from, and what we are not doing

There is an existing community integration, `alceasan/ha-deepgram-tts`, forked to
`samgutentag/ha-deepgram-tts` and checked out at `~/Developer/ha-deepgram-tts`. It was audited in
full on 2026-09-15. **We are not building on it.** The fork stays on the personal account as a
credited reference and is not deleted.

Three reasons, in order of weight:

1. **Almost nothing survives.** Of roughly 850 lines of Python, the plan that came out of the
   audit deletes 206 outright (`stream_processor.py`) and substantially rewrites another ~550. A
   generous estimate of surviving lines is around 180, about a fifth, and most of that is the
   config-flow shape. The genuinely valuable part of that repo is *knowledge*, and knowledge
   transfers in this document, not in a diff.
2. **The history is worth more than the code.** The lab convention flips a shipped project into a
   public repo with history rewritten into build order so the commit log reads as a tutorial. A
   fresh build writes that history correctly the first time. A fork's history opens with someone
   else's initial commit and five repair commits, and rewriting it into a tutorial is fighting the
   material.
3. **A fork cannot go private.** GitHub does not offer this. Making a parent private *detaches*
   its forks rather than converting them, forks stay public, and there is no documented self-serve
   way to leave a fork network. So "just flip it private so the hub can live in it" was never
   actually available.

The fork was also carrying leftover `ludeeus/integration_blueprint` scaffolding: duplicate
function definitions, three dead exception classes, docstrings still describing the blueprint, and
a mix of English and Spanish comments. Inheriting that means inheriting somebody's unfinished
refactor.

## Why the repo lives here

`~/LABS` is the work-account tree (`samgutentag-deepgram`), private by convention, `-lab` suffix
mandatory. Identity comes from `includeIf gitdir:~/LABS/` and resolves to
`307399679+samgutentag-deepgram@users.noreply.github.com`. Verified on init; there is no repo-local
`user.email` and there must never be one.

This is the tree where `.hub/` and `advocacy/` are native, which is the whole reason for the move.
The personal fork is public, and a build ledger that quotes decisions and calls cannot live in a
public repo.

Flip target when it ships: a clean public `samgutentag-deepgram/ha-deepgram-tts`. No collision with
the personal fork of the same name; different account.

**Note on tooling drift:** `~/.claude/CLAUDE.md` says the active `gh` account is the work one and
tells you to reach for the personal token. That is now backwards. `gh auth status` shows
`samgutentag` active and `samgutentag-deepgram` inactive, so anything touching this repo's remote
needs the *work* token, not the personal one. Worth correcting in that file.

---

## Verified facts about the Deepgram API

All of this was confirmed live on 2026-09-15 by unauthenticated probe against `api.deepgram.com`,
which returns real parameter validation before it checks auth. Do not re-derive it from the docs;
the docs are thinner than this.

### Endpoints

| Thing | Value |
| --- | --- |
| Flux batch | `POST https://api.deepgram.com/v2/speak` |
| Flux streaming | `wss://api.deepgram.com/v2/speak` |
| Aura batch | `POST https://api.deepgram.com/v1/speak` |
| Flux voice catalog | `GET https://api.deepgram.com/v2/models` (public, no auth, HTTP 200) |
| Aura voice catalog | `GET https://api.deepgram.com/v1/models` (public, no auth, HTTP 200) |

### The families do not mix

Posting an Aura model to `/v2/speak` returns HTTP 400 `V1_MODEL_ON_V2_SPEAK_ENDPOINT`, and that
check runs *before* auth. So the client routes on the model id: `flux-*` to v2, everything else to
v1. One synthesize signature, two URLs.

### Voice catalogs

- `/v2/models` returns exactly **36** `flux-tts` voices, all English (`en`, `en-US`, plus regional
  `en-AU`, `en-GB`, `en-IE`, `en-IN`, `en-PH`, `en-SG`). `flux-marcus-en` and `flux-brittany-en`
  are both in it.
- `/v1/models` returns **102** TTS models: 90 `aura-2` plus 12 legacy `aura`. Languages: en, es,
  de, fr, nl, it, ja. Zero Flux entries, which is why the fork's dynamic voice discovery could
  never see Flux at all.
- Each entry carries `canonical_name`, `name`, `architecture`, `languages`, and a `metadata` object
  with `display_name`, `accent`, `age`, `tags`, `use_cases`, and a `sample` URL. Use
  `metadata.display_name` for anything a person reads; `name` is the bare lowercase given name.
- **Language codes are hyphenated** (`en-US`, `es-419`). Never split on underscore. The fork did,
  in five places, which is why its language dropdown showed a mix of base and regional codes.

### `/v2/speak` query parameters

Enumerated by sending deliberately invalid values and reading the rejections.

| Param | Values |
| --- | --- |
| `model` | required. `flux-*` only |
| `encoding` | `linear16`, `mulaw`, `alaw`, `mp3`, `opus`, `flac`, `aac`. Default `mp3` |
| `container` | `wav`, `ogg`, `none` |
| `sample_rate` | rejected when `encoding=mp3` ("not applicable") |
| `speed` | 0.5 to 1.5, 0.05 increments |
| `bit_rate`, `mip_opt_out`, `callback` | accepted |

Unknown params are rejected outright with `INVALID_QUERY_PARAMETER`. Compressed and containerized
encodings are batch-only; the socket emits raw `linear16`, `mulaw`, or `alaw`.

Body is `Content-Type: application/json` with `{"text": "..."}`.

### Flux TTS websocket protocol

Client messages:

- `{"type":"Speak","text":"..."}`
- `{"type":"Flush"}` finishes the turn
- `{"type":"Interrupt","playback_offset":{"type":"time_ms","value":2340}}`
- `{"type":"Configure","speed":1.15}`
- `{"type":"Close"}`

Server messages: `Connected`, `SpeechStarted`, `SpeechMetadata`, `SpeechInterrupted`, `Flushed`,
`SessionMetadata`, `ConfigureSuccess`, `ConfigureFailure`, `Warning`, `Error`.

Every audio frame for a turn arrives between `SpeechStarted` and `SpeechMetadata`, as binary frames
interleaved with JSON text frames. `SpeechInterrupted` carries `text_spoken` and `text_remaining`.

**The server places flush boundaries internally.** This is the single most important fact in this
document: it means no sentence splitting, no per-sentence round trips, and no audio fragment
stitching on our side. Stream LLM tokens in, take audio out.

---

## Verified facts about Home Assistant

From `home-assistant/core` @ `dev`, read 2026-09-15.

- Version `2026.10.0.dev0`, so current stable is 2026.9.x.
- `requires-python = ">=3.14.2"`.
- `aiohttp==3.14.3`. **`async_timeout` is not in core requirements** and aiohttp dropped it as a
  dependency at 3.10. Use `asyncio.timeout()`.
- `audioop-lts==0.2.2` *is* in core, so pydub would import on 3.13+ if it were installed. It is not
  an HA dependency. We do not need it either way.
- `python-slugify` is available.

### The TTS entity contract

```python
@dataclass
class TTSAudioRequest:
    language: str
    options: dict[str, Any]
    message_gen: AsyncGenerator[str]

@dataclass
class TTSAudioResponse:
    extension: str
    data_gen: AsyncGenerator[bytes]
```

- `async_supports_streaming_input()` **auto-detects** by comparing
  `self.__class__.async_stream_tts_audio` against the base method. Overriding the method is all it
  takes; there is no flag to set. This is why the fork's broken streaming path was the one Assist
  always took.
- `Voice` is `@dataclass(frozen=True)` with fields `voice_id, name`, imported from
  `homeassistant.components.tts.models`.
- `supported_options` and `default_options` are `@cached_property`, returning `list[str] | None`
  and `Mapping[str, Any] | None`.
- Option constants worth supporting: `ATTR_VOICE` (`"voice"`), `ATTR_PREFERRED_FORMAT`
  (`"preferred_format"`), `ATTR_PREFERRED_SAMPLE_RATE`. Default format is `mp3`.
- HA converts audio itself in `_async_convert_audio` whenever the requested format differs from
  what the entity returns. So returning WAV and letting HA transcode is fine, and doing our own
  transcode is waste.
- Manifest keys worth knowing: `single_config_entry: true` is the sanctioned way to express
  single-instance. Do **not** express it with a hardcoded `unique_id`, which is what the fork did
  and which blocks running a Flux entity and an Aura entity side by side. We want both, so neither.
- `OptionsFlow.config_entry` is a read-only property set by the framework since 2025.12. Never
  define an `__init__` that takes or assigns it.
- `iot_class`: the closest core analog is `elevenlabs`, which uses `cloud_polling`.

---

## Design decisions, already settled

Do not relitigate these. They came out of a full audit plus live API probing.

1. **Route by model prefix.** `flux-*` to `/v2/speak`, everything else to `/v1/speak`.
2. **Merge both catalogs into one voice list**, keyed by `canonical_name`, labeled from
   `metadata.display_name`, each entry tagged with its family so the UI can group them.
3. **Default voice is `flux-haley-en`.** American, young adult, professional and empathetic per its
   metadata, and the voice Deepgram's own quickstart uses, so it is the most recognizable default.
4. **Non-English never resolves to Flux.** `supported_languages` is the union of both families, and
   voice resolution for es, de, fr, nl, it, or ja must return an Aura-2 voice.
5. **Streaming is the websocket, with a batch fallback.** Fall back to `/v2/speak` batch when the
   socket fails or when the selected voice is Aura, so a dropped connection degrades instead of
   erroring.
6. **WAV out of the socket.** The socket gives raw `linear16` with no container, so prepend a WAV
   header and report `extension="wav"`. Advertise `preferred_format` and let HA handle the rest.
7. **Speed is Flux-only.** Hide or ignore the option when an Aura voice is selected.
8. **Barge-in is out of scope.** `SpeechInterrupted.text_spoken` is the right primitive, but HA's
   TTS entity API has no barge-in hook today. Note it; do not build it.

### One engineering note on voices

`flux-marcus-en` and `flux-brittany-en` drift in pitch and volume between calls, sometimes emit an
audible musical note before a greeting, and can click at clip starts. A home assistant makes many
short separate calls, which is exactly where that drift is most audible, so neither is a good
shipped default. Both are cleared for use and fine to offer in the picker. This is engineering
advice about defaults, not a permission question, and it is settled.

---

## Build order

Seven chapters. Written as build order on purpose, so the eventual public history reads as a
tutorial with no rewrite needed.

| # | Chapter | Lands |
| --- | --- | --- |
| 1 | Scaffold | `manifest.json` with real requirements, `hacs.json`, `const.py`, `strings.json`, `translations/en.json`, hassfest and HACS CI, ruff, a `tests/` skeleton |
| 2 | API client | Two endpoints, JSON bodies, typed errors, `asyncio.timeout` |
| 3 | Voice catalog | Fetch and merge `/v1/models` and `/v2/models` |
| 4 | Config flow | API key step, voice picker, options flow, multiple entries allowed |
| 5 | TTS entity, batch | Flux default, language routing, `async_get_tts_audio` against `/v2/speak` |
| 6 | TTS entity, streaming | Websocket client, `async_stream_tts_audio`, WAV header, batch fallback |
| 7 | Harden | Real-hardware test notes, README, CHANGELOG, first tag |

Chapter 6 is the only one with real design risk. Everything before it is mechanical.

Get chapter 5 onto the real Home Assistant instance before starting 6. A working batch path on real
hardware is the thing that makes the streaming work verifiable rather than theoretical.

---

## Still unverified

Carry these forward; they are not resolved.

1. **No API key was available in the audit session.** Nothing past the auth check has been
   exercised. Every endpoint fact above comes from unauthenticated probes and the docs. First real
   task in chapter 2 is a single authenticated round trip against both `/v1/speak` and `/v2/speak`.
2. **First-frame latency over the socket is unmeasured.** Deepgram's marketing claims audio starts
   in as low as 80ms. Treat that as a claim to test, not a fact to repeat, and measure it on the Pi
   rather than on a laptop.
3. **Whether `/v1/speak` rejects a `text/plain` body** is unknown, because auth is validated before
   the body and a dummy key always returns 401. Only matters for the Aura path.

---

## Next steps

1. `/project-hub init` in this repo. Writes `.hub/` and wires it to Asana, which is an outward
   action, so it needs Sam's go-ahead.
2. `/advocacy-intake` once there is a result worth claiming. `advocacy-cycle` refuses to run
   without a frozen claim and an Asana entry, so intake gates the content work. Do not start it
   before chapter 5 is on real hardware; there is nothing honest to claim yet.
3. Create the private remote on the **work** account, per the note about `gh` account drift above.
4. Chapter 1.

## Reference material carried over

In `docs/`:

- `state-of-the-fork-2026-09-15.html` — the full audit of the community integration. The evidence
  behind "we are not building on it."
- `flux-first-rewrite-plan.md` — the 16-commit repair plan written for the fork. Superseded by the
  build order above, kept because its code review section is the most detailed record of what that
  codebase actually does.
- `eli5-flux-first-plan.html` — eleven diagrams covering the same ground. Good raw material for a
  later write-up.
