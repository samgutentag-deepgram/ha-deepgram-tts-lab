# Flux-first rewrite plan

Plan of record for modernizing the `ha-deepgram-tts` fork. Written 2026-09-15 against
`ba59415`. Supersedes nothing; the audit at `docs/state-of-the-fork-2026-09-15.html` is the
input to this.

Goal: Flux TTS is the primary path and the default voice. Aura-2 stays fully supported as a
second family, because every Flux voice is English and Aura-2 is the only way to serve a
non-English Assist pipeline.

---

## 0. Decision: the repo does not move

Asked: should this working directory migrate to the lab tree so the advocacy pipeline can run
on it.

Answer: no, and there are three independent reasons, any one of which is sufficient.

1. **Git identity.** `~/.gitconfig` routes `gitdir:~/Developer/` to `.gitconfig-personal` and
   `gitdir:~/LABS/` to `.gitconfig-work`. This repo currently commits as
   `1404219+samgutentag@users.noreply.github.com`, which is correct for a fork on the personal
   `samgutentag` account. Moving the directory silently reassigns authorship to the work
   identity. Worse, the *global* default is already the work account, so anything placed
   outside `~/Developer/` or `~/TINKER/` inherits work identity by default rather than by
   choice.
2. **What the lab tree is.** `~/LABS/CLAUDE.md` defines it as "everything on the
   `samgutentag-deepgram` account." This fork is not on that account and, per the ask, is not
   going to be.
3. **The suffix invariant.** Normalized 2026-08-26: in `~/LABS`, `-lab` means private and a
   bare name means public. A bare `ha-deepgram-tts` sitting there would read as the public
   snapshot of a lab that never existed, which the same file explicitly forbids ("a `-lab`
   twin is never invented to fake build history").

### How content gets made anyway

The code repo and the campaign repo are different artifacts and belong in different trees.

- Code stays at `~/Developer/ha-deepgram-tts`, personal identity, public fork.
- When there is something worth saying, run `/advocacy-intake` in a new campaign lab at
  `~/LABS/flux-tts-home-assistant-lab`. That lab holds only `advocacy/`, `.hub/`, and the
  ledger. It reads the code repo; it does not contain it.

Name it for the campaign, not the repo. `ha-deepgram-tts-lab` would imply a twin of the code
repo and drag in the pair convention that does not apply here.

Note the ordering constraint: `advocacy-cycle` refuses to run without a frozen claim from
`advocacy-intake` and an Asana entry. So the campaign starts after Phase 2 lands and there is
a real result to claim, not now.

---

## 1. Code review findings

Severity: **B** blocks loading or a core path, **C** correctness, **P** polish.

### `custom_components/deepgram_tts/api.py`

| Sev | Line | Finding |
| --- | --- | --- |
| B | 9, 84, 118 | `import async_timeout` and two `async_timeout.timeout()` calls. Not in HA core requirements, not declared in the manifest, and aiohttp dropped it as a dependency at 3.10. Replace with `asyncio.timeout()`. |
| C | 78, 87, 111 | Sends `Content-Type: text/plain` with a raw UTF-8 body. The `/v1/speak` reference specifies `application/json` with `{"text": "..."}`. |
| C | 138-141 | The broad `except Exception` catches `DeepgramTTSApiClientAuthenticationError` raised by `_verify_response_or_raise` two lines up and rewraps it as a generic `DeepgramTTSApiClientError`. Callers can no longer tell an expired key from a network fault. Reraise the client's own exception types before the broad handler. |
| C | 69 | `_base_url` is a single hardcoded endpoint. Flux needs `/v2/speak` and Aura needs `/v1/speak`, chosen per request. |
| P | 12-35 | Three dead `IntegrationBlueprintApiClient*` exception classes. |
| P | 28-35, 50-55 | `_verify_response_or_raise` is defined twice. The second definition silently wins. |
| P | 92-93 | `except Exception as exc: raise` with an unused binding. |
| P | 98, 107 | Default model hardcoded to `aura-2-thalia-en` in two places. Becomes a Flux default and should live in `const.py`. |

### `custom_components/deepgram_tts/api_models.py`

| Sev | Line | Finding |
| --- | --- | --- |
| B | 4, 12 | Same `async_timeout` blocker. |
| C | 9 | Only fetches `/v1/models`, which contains zero Flux entries. Flux voices come from `/v2/models`. |
| P | 13-15 | Raises raw `aiohttp` errors, so callers cannot distinguish auth from transport. |

### `custom_components/deepgram_tts/__init__.py`

| Sev | Line | Finding |
| --- | --- | --- |
| C | 43 | `await models_client.fetch_models()` is unguarded. A raw aiohttp error escapes `async_setup_entry`, which marks the entry failed with no retry. Should raise `ConfigEntryNotReady`. |
| P | 1-6 | Docstring still describes `integration_blueprint`. |
| P | 10 | `from datetime import timedelta`, unused. |
| P | 20 | `from .tts import DeepgramTtsEntity`, unused, and an unnecessary import edge into the platform module. |
| P | 44 | Assigns `client._models_cache` from outside the class. Pass the catalog to the constructor. |

### `custom_components/deepgram_tts/tts.py`

| Sev | Line | Finding |
| --- | --- | --- |
| B | 165-171 | `message_gen()` accumulates every chunk of `request.message_gen` into one string and yields it once. The whole response is buffered before the first synthesis call, which removes the entire point of the streaming API the README advertises. |
| C | 72, 101 | `lang.split("_")[0]` to derive a base language. Deepgram language codes use hyphens (`en-US`, `es-419`), never underscores, so this is a no-op and `supported_languages` returns a mix of base and regional codes. Must be `split("-")[0]`. |
| C | 128-132 | Unreachable. `voice` was already defaulted at 120-121, so `if not voice` can never be true. |
| C | 141 | Hardcodes `return "mp3", audio_bytes`, ignoring any requested format. |
| C | 129 | Reaches through two private attributes: `self._processor._client._models_cache`. |
| P | 114-134, 153-163, 86-92 | Voice resolution is written three times with slightly different fallbacks. Extract one helper. |
| P | 102 | `Voice(canonical_name, model["name"])` uses the bare lowercase given name. `metadata.display_name` is the presentable one. |
| P | 79-81 | `supported_options` exposes only `voice`. No `preferred_format`, no `speed`. |
| P | 7, 10, 41-43, 57-60 | Unused `re` import; a stale Spanish comment about deleted code; a no-op `async_setup`; `_default_voice` and `_default_language` assigned and never read. |

### `custom_components/deepgram_tts/stream_processor.py`

Whole file is slated for deletion in Phase 2. Recorded so the deletion is justified rather
than assumed.

| Sev | Line | Finding |
| --- | --- | --- |
| B | 9-12, 149-150 | Optional pydub import leaves `AudioSegment = None`, then `async_process_stream` raises `RuntimeError("pydub is not available")`. pydub is not an HA dependency and is not declared, so this raises on every streaming request. |
| C | 164-168 | Decodes each MP3 fragment and re-exports it as MP3. A full transcode per sentence for no benefit. HA already converts in `_async_convert_audio` when the requested format differs. |
| C | 80 | `min_len = 2 ** count * 10`, where `count` increments per input chunk. By chunk 20 the threshold is 10 MB. Harmless today only because the caller yields exactly one chunk. |
| C | 176-178 | Cancels the producer task and `await asyncio.sleep(0)` instead of awaiting the cancellation. Leaks a pending task on teardown. |
| P | 17, 112-132 | `TRIM_MS_FROM_END = 0` makes `_trim_end_of_audio` dead code. |
| P | 134-140 | `_strip_id3` is defined and never called. |
| P | 18 | `SYNTHESIS_DELAY_S = 0.15` sleeps before every synthesis call. |
| P | 44-54 | Decimal-placeholder regex hack, and the splitter still breaks on "Dr." and "3 p.m.". |
| P | 171 | `task_done()` with no corresponding `join()`. |

### `custom_components/deepgram_tts/config_flow.py`

| Sev | Line | Finding |
| --- | --- | --- |
| C | 32-55 | `async_step_connection_test` is dead. HA enters at `async_step_user` and nothing routes to it. |
| C | 178, 189, 212 | Same `split("_")` language bug as `tts.py`. |
| C | 87 | `async_set_unique_id("deepgram_tts")` is a hardcoded constant, so a second entry can never be created. Blocks running one Flux entity and one Aura entity side by side. Use the manifest's `single_config_entry` key if single-instance is actually wanted; here it is not. |
| P | 163-164 | `DeepgramTTSOptionsFlowHandler.__init__` takes `config_entry` and does `pass`. This dodges the 2025.12 breaking change by accident, since that fires on *assigning* `self.config_entry`. Delete the override and the argument. |
| P | 93 | Stashes the API key in `self.context`. Use an instance attribute. |
| P | 11 | `from slugify import slugify`, unused. |
| P | 132 | Uses `model["name"]` rather than `metadata.display_name`. |
| P | - | No `strings.json` and no `translations/`, so both flows render bare step ids. |

### Repo level

| Sev | File | Finding |
| --- | --- | --- |
| B | `manifest.json` | `"requirements": []` while the code imports `async_timeout` and `pydub`. Root cause of both blockers. |
| P | `manifest.json` | Codeowner `@alceasan` and the upstream issue tracker. `iot_class: cloud_push`; the closest core analog, `elevenlabs`, uses `cloud_polling`. |
| P | `hacs.json` | Floor still 2025.7.0. Current stable is 2026.9.x. |
| P | - | Zero git tags, so HACS has no release to resolve and falls back to the branch. |
| P | `.devcontainer.json` | Builds from a `Dockerfile` that is not in the repo. |
| P | `requirements.txt` | `pytest-homeassistant-custom-component==0.13.89`, black, flake8. Years stale; HA core uses ruff. |
| P | - | No `tests/` directory, though `requirements.txt` installs pytest. |
| P | `CHANGELOG.md` | 1.0.2 dated 2026-08-01 but committed 2026-01-08. 1.0.1 dated 2025-01-10 but committed 2025-10-01. |
| P | `README.md` | HACS instructions say `alceasan/ha-deemgram-tts`. Claims working 2025.7 streaming support. |

---

## 2. Flux design decisions

Settled now so the commits below do not relitigate them.

**Endpoint routing by model prefix.** `/v2/speak` rejects Aura models with
`V1_MODEL_ON_V2_SPEAK_ENDPOINT` before it even checks auth, and `/v1/speak` does not serve
Flux. So the client picks the endpoint from the model id: `flux-*` goes to v2, everything else
to v1. One `async_synthesize_speech` signature, two URLs.

**Two catalogs, one voice list.** `/v1/models` for Aura, `/v2/models` for Flux, both public and
unauthenticated. Merge into one list keyed by `canonical_name`, label from
`metadata.display_name`, and tag each entry with its family so the UI can group them.

**Default voice is Flux.** `flux-haley-en` as the shipped default: American, young adult,
professional and empathetic per its metadata, and it is the voice the Deepgram quickstart uses,
so it is the one most likely to be recognized. Any of the 36 is available.

**English collapses to Flux, everything else falls back to Aura.** Every Flux voice is English
only. When an Assist pipeline asks for `es`, `de`, `fr`, `nl`, `it`, or `ja`, the only
candidates are Aura-2. `supported_languages` is the union of both families, and voice
resolution for a non-English language must never return a Flux id.

**Streaming is the websocket, with a batch fallback.** `wss://api.deepgram.com/v2/speak`, with
`Speak` per chunk, `Flush` when `request.message_gen` is exhausted, and binary frames yielded
until `SpeechMetadata`. The server places the flush boundaries, which is what makes
`stream_processor.py` deletable: no sentence regex, no per-sentence round trips, no fragment
stitching. If the socket fails or the selected voice is Aura, fall back to the batch endpoint
so a dropped connection degrades instead of erroring.

**Container: WAV out of the socket.** The socket emits raw `linear16` with no container, so the
entity prepends a WAV header and reports `extension="wav"`. Advertise `preferred_format` in
`supported_options` and let HA's ffmpeg conversion handle anything else.

**Speed is Flux-only.** `Configure` accepts `speed` from 0.5 to 1.5 in 0.05 steps, and the
batch endpoint takes it as a query param. Aura has no equivalent, so the option must be hidden
or ignored when an Aura voice is selected.

**Not in scope.** `SpeechInterrupted` carries `text_spoken` and `text_remaining`, which is the
right primitive for Assist barge-in, but HA's TTS entity API has no barge-in hook today. Note
it and move on.

One engineering note on voice choice, not a gate: `flux-marcus-en` and `flux-brittany-en` drift
in pitch and volume between calls, sometimes emit an audible musical note before a greeting,
and can click at clip starts. A home assistant makes many short separate calls, which is
exactly where that drift is most audible, so neither is a good shipped default. Both are fine
to offer.

---

## 3. Commit sequence

Sixteen commits in three chains, one component each. Chain A must merge before chain B rebases
onto it.

### Chain A: unbreak (branch `fix/unbreak-runtime`)

| # | Commit | Touches |
| --- | --- | --- |
| A1 | `fix(deps): replace async_timeout with asyncio.timeout` | `api.py`, `api_models.py`, `manifest.json` |
| A2 | `fix(setup): raise ConfigEntryNotReady when the catalog is unreachable` | `__init__.py` |
| A3 | `fix(api): send JSON bodies and stop swallowing auth errors` | `api.py` |
| A4 | `fix(lang): split language codes on hyphen, not underscore` | `tts.py`, `config_flow.py` |
| A5 | `refactor: drop integration_blueprint scaffolding and dead code` | `api.py`, `const.py`, `__init__.py`, `tts.py`, `config_flow.py` |

A1 is the one that makes the integration load at all. Stop after A5 and install on the real
instance before starting chain B.

### Chain B: Flux (branch `feat/flux-tts`, worktree)

| # | Commit | Touches |
| --- | --- | --- |
| B1 | `feat(api): route flux models to /v2/speak and aura to /v1/speak` | `api.py`, `const.py` |
| B2 | `feat(models): merge the v1 and v2 voice catalogs` | `api_models.py` |
| B3 | `feat(tts): default to flux and centralize voice resolution` | `tts.py`, `const.py` |
| B4 | `feat(tts): add a speed option for flux voices` | `tts.py`, `config_flow.py` |
| B5 | `feat(config): allow multiple entries and migrate stored options` | `config_flow.py`, `__init__.py` |
| B6 | `feat(stream): synthesize over the flux websocket` | new `ws_client.py`, `tts.py` |
| B7 | `refactor(stream): delete stream_processor.py` | removes the file and the last pydub reference |

B6 is the only commit with real design risk. Everything before it is mechanical.

### Chain C: hygiene (branch `chore/repo-hygiene`, worktree)

| # | Commit | Touches |
| --- | --- | --- |
| C1 | `chore(meta): retarget ownership and bump the HA floor` | `manifest.json`, `hacs.json` |
| C2 | `feat(i18n): add strings.json and en translations` | new `strings.json`, `translations/en.json` |
| C3 | `docs: rewrite README and CHANGELOG for this fork` | `README.md`, `CHANGELOG.md` |
| C4 | `chore(ci): move to ruff, add tests, fix the devcontainer` | `requirements.txt`, `.devcontainer.json`, `tests/`, `.github/workflows/` |

C1 and A1 both touch `manifest.json`, on different keys. Land A1 first and the rebase is
trivial.

---

## 4. Worktrees

Two, not one per chain. Chain A is a tight sequential edit over the same four files, so a
worktree for it buys nothing but a rebase.

```
~/Developer/ha-deepgram-tts            main, and chain A directly on a branch here
~/Developer/ha-deepgram-tts--flux      feat/flux-tts        chain B
~/Developer/ha-deepgram-tts--hygiene   chore/repo-hygiene   chain C
```

Both worktrees are siblings under `~/Developer/` on purpose. The global git identity is the
**work** account; the personal identity is applied only by `includeIf gitdir:~/Developer/` and
`gitdir:~/TINKER/`. A worktree anywhere else would commit to a personal repo as
`samgutentag-deepgram`.

Chain C can start immediately and in parallel, since it touches no Python that chains A or B
touch. Chain B should wait for A to merge.

---

## 5. Verification

Before any code, confirm the diagnosis on the real instance:

1. In the HA container, `python -c "import async_timeout"` and `python -c "import pydub"`. Two
   failures confirms both blockers.
2. Install the fork as-is, restart, and grep the log for `ModuleNotFoundError` during setup of
   `deepgram_tts`.
3. If it loads, call `tts.speak` once directly (should work), then run the same text through an
   Assist pipeline (should raise the pydub `RuntimeError`). That split is the signature.

After each chain:

- **A:** entry loads, `tts.speak` produces audio with an Aura voice, Assist pipeline no longer
  raises. Language dropdown shows base codes only, not a mix of `en` and `en-US`.
- **B:** `flux-haley-en` is the default on a fresh install, a Spanish pipeline still resolves an
  Aura voice, and the first audio frame arrives before the LLM has finished its sentence.
- **C:** hassfest and HACS validation both pass, config flow shows real labels, `pytest` runs.

### Still unverified

There is no Deepgram API key on this machine, so nothing past the auth check has been
exercised. Every endpoint fact here comes from unauthenticated probes, which do return real
parameter validation, plus the docs. Two specifics that need a key: whether `/v1/speak` actually
rejects `text/plain`, and the real first-frame latency over the socket.
