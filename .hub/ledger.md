# Build ledger

Append-only. Records what a repo scan cannot recover: the choice and what it cost, the symptom
before anyone knew the cause, the thing tried and reverted, the claim and whether it held.

Read the whole file before appending. Never rewrite it. Corrections are new entries, never edits.

Tags: `decision` `friction` `deadend` `surprise` `claim` `asset`

Every entry carries a `Source:` line and a `Routes to:` line. A number without a source cannot
be used in a post, and that is what makes this file publishable.

---

## 2026-09-15

### [decision] Chapters 2 through 6 built in parallel behind a frozen interface contract
The build order in HANDOFF section 6 is seven sequential chapters, and sequential is the right
shape for the eventual public commit log. It is the wrong shape for one afternoon. What lost:
building 2 through 6 in order, which would have finished maybe two of them. What was chosen:
freeze every module boundary and signature first, in `docs/superpowers/interface-contract.md`,
then hand each chapter to its own agent in its own git worktree with an explicit list of files
it owns and a hard instruction not to touch a file it does not own.
What it cost: about forty minutes of writing the contract before any parallel work could start,
plus the merge afterward. What it bought: file-level disjointness, so merging is a fast-forward
of new files rather than a conflict resolution. The contract is also the artifact that makes the
sequential public history possible later, because the chapter boundaries are already written down.
The risk taken knowingly: an agent discovers the contract is wrong about something and either
follows it into a bad design or deviates silently. Mitigation was asking each one to report
anything in the contract that turned out wrong or underspecified, as a named deliverable.
Source: docs/superpowers/interface-contract.md · git log --oneline
Routes to: technical blog post, the "how this got built" section

### [friction] The entry would not load, and the error named a file nobody planned to write
Symptom: three of the four chapter 1 tests failed with `Platform deepgram_tts.config_flow not
found`, and the config entry never reached LOADED. Cause: `manifest.json` sets
`"config_flow": true`, and Home Assistant treats that as a promise that the module exists. It
imports `config_flow` during entry setup, not only when a user clicks Add Integration. The
chapter 1 file list in the starter prompt does not include `config_flow.py`, because the config
flow is chapter 4. Fix: chapter 1 grew the minimum a manifest with `config_flow: true` is
allowed to ship, which is one API key step with no validation. Chapter 4 adds key verification,
the voice picker, and the options flow on top of it.
Worth knowing generally: `config_flow: true` and a missing `config_flow.py` is not a config flow
bug, it is an integration-will-not-load bug, and the error message points at the wrong chapter.
Source: custom_components/deepgram_tts/config_flow.py · tests/test_init.py
Routes to: technical blog post, the HACS integration gotchas section

### [friction] Two more missing modules, and neither of them is ours
Symptom: after the config flow fix, the entry still failed, first with
`ModuleNotFoundError: No module named 'mutagen'` and then with the same for `haffmpeg`. Cause:
both belong to `homeassistant.components.tts`, which our platform forwards to. Home Assistant
installs a component's requirements at runtime; the test harness does not. Fix: both went into
`requirements-test.txt` with a comment saying why.
The part that matters: they must **not** go into `manifest.json` requirements. They are the tts
component's dependencies, not ours, and ours is still correctly empty. Declaring somebody else's
dependency is how a manifest starts lying, and a lying manifest is exactly what stopped the
community integration this project replaces from loading at all.
Source: requirements-test.txt · custom_components/deepgram_tts/manifest.json
Routes to: technical blog post

### [surprise] Setting up the second config entry raised OperationNotAllowed
Expected: `async_setup(entry_a)` then `async_setup(entry_b)` to load two entries. Actual: the
second call raised `OperationNotAllowed`, because setting up the domain at all loads every entry
that domain owns. Both entities were already registered by the time the second call ran, which
the log showed plainly: `tts.deepgram_flux_haley` and `tts.deepgram_aura_celeste`.
Not a bug, and the test is better for it: the thing worth proving is that two entries coexist,
not that a particular sequence of setup calls succeeds. The test now asserts both entries reach
LOADED and that two `tts` entities exist.
Source: tests/test_init.py::test_two_entries_can_coexist
Routes to: technical blog post, the multiple-entries section

### [friction] hassfest cannot run on this machine, so the check that matters got written locally
Symptom: `hassfest` is the gate on HACS distribution and there was no way to run it before
pushing. Cause: it ships as a Docker action, `docker` is installed here but no daemon is running.
Fix: `scripts/manifest_check.py`, stdlib only, covering the three checks whose failure is
expensive: manifest keys present and in hassfest's order, `strings.json` and
`translations/en.json` having identical key trees, and every third-party import being declared
in manifest requirements or being stdlib or HA-provided.
The third check is the point. The community integration this replaces declared
`"requirements": []` while importing `async_timeout` and `pydub`, neither of which HA ships, and
it almost certainly never loaded. That failure is now a CI-visible error instead of a discovery.
hassfest and HACS validation still run in CI; this does not replace them, it just fails faster.
Source: scripts/manifest_check.py · .github/workflows/validate.yml
Routes to: technical blog post, and a standalone gotchas post about custom integration manifests

### [surprise] ruff 0.16 reformats Python code blocks inside markdown
Expected: `ruff format --check .` to look at `.py` files. Actual: it wanted to reformat
`HANDOFF.md`, because it now formats embedded Python code blocks in markdown, and the handoff
quotes Home Assistant source with the blank-line spacing of the original.
Fixed by excluding `*.md` in `pyproject.toml`. Worth flagging for anyone who turns ruff format
loose on a repo with prose in it: the handoff's quoted source is verbatim on purpose and a
formatter silently rewriting quoted material is worse than a lint failure.
Source: pyproject.toml, tool.ruff extend-exclude · `uvx ruff@0.16.7 format --check .`
Routes to: gotchas post

### [claim] Chapter 1 loads against real Home Assistant 2026.9.2, and it held
Six tests pass: the entry loads and unloads, an unreachable voice catalog lands in SETUP_RETRY
rather than SETUP_ERROR, two entries coexist, and the language code split is on a hyphen.
Run against Home Assistant 2026.9.2 on Python 3.14.0 with
pytest-homeassistant-custom-component 0.13.365, not against a mock of Home Assistant.
Not yet verified, and both need a key that does not exist on this machine: any authenticated
request, and anything at all on real hardware.
Source: `.venv/bin/pytest -q` → `6 passed in 0.14s` · commit 325d6d7
Routes to: technical blog post, chapter 1 section

### [decision] No Asana project and no advocacy intake, both queued for Sam instead
Sam said to start the hub and kick off the advocacy cycle. Two parts of that were held back on
purpose and it is worth recording why rather than letting it read as an omission.
`project-hub init`'s Asana step creates a team-visible project plus four tasks, and one of the
four needs a check-back date that only he can pick. It is outward facing and it was not worth
guessing while he was away. Everything else in `.hub/` is complete and works without it.
`advocacy-intake` freezes the claim, and `advocacy-cycle` will not run without a frozen one.
HANDOFF section 8.5 gates intake on chapter 5 running on real hardware, because before that
there is nothing honest to claim. He owns zero speaker devices today, so that gate is real and
not procedural. What got built instead: `advocacy/prep/`, which is every fact, angle, outline,
draft, and video script staged so intake is a short job rather than a cold start.
Source: .hub/hub.yml, the comment where the asana key would go · HANDOFF.md section 8.5
Routes to: the conversation when he is back, and the intake session after that

### [friction] The project-hub template ships with orphaned CSS
Symptom: three CSS declaration lines sitting at the top level of `template.html`'s stylesheet
with no selector, right after the comment describing the objectives board. Cause: the objectives
board was removed from the skill on 2026-08-26 and its selectors went with it, but three of its
declaration bodies were left behind.
Harmless in practice, because CSS error recovery discards each orphan at the next brace and
`.stamp` onward still parses. Copied verbatim anyway, because the skill's rule is that the chrome
is canonical and not to be re-derived, and quietly fixing a template through one repo's copy of
it is how two copies start to drift.
Source: ~/.claude/plugins/marketplaces/project-workflow/skills/project-hub/template.html, the block after the "Board:" comment
Routes to: a fix in the project-workflow plugin, not in this repo

### [claim] The live catalogs match the handoff's numbers exactly, six weeks after they were recorded
HANDOFF section 3.3 recorded 36 Flux voices from `/v2/models` and 102 Aura TTS entries from
`/v1/models`, split 90 `aura-2` and 12 legacy `aura`, probed on 2026-09-15. Re-fetched live from
a different session against the real API: 36 and 102, with the same 90/12 split.
It held. Worth stating as a claim rather than an assumption, because the whole voice list is
fetched at runtime and nothing in the code hardcodes a count. The numbers appearing in prose
later are now checked twice against the live API rather than once.
Source: `scripts/live_check.py` unauthenticated half · HANDOFF.md section 3.3
Routes to: technical blog post, the voice catalog section

### [surprise] aioclient_mock loses to a fixture that resolves too early
Expected: an `aioclient_mock` fixture plus a client fixture to intercept every request. Actual:
`'NoneType' object has no attribute 'getaddrinfo'`, which names nothing useful and looks like a
DNS problem. Cause: `hass` caches the aiohttp session the first time anything asks for one, so a
**synchronous** client fixture resolves before the mock patch is in place, gets a real session,
and tries to hit the network for real.
Fix: the client fixture has to be `async` and has to depend on `aioclient_mock` explicitly, so
ordering is a declared dependency rather than luck. Also worth knowing: `mock_calls` records
tuples of `(method, url, data, headers)` with the method upper-cased, so asserting on `"post"`
silently never matches.
This will bite every remaining chapter that builds a client or a catalog fetch in a fixture, so
it is written down here rather than rediscovered three more times.
Source: tests/test_api.py, the client fixture · chapter 2 agent report
Routes to: a gotchas post about testing Home Assistant custom integrations

### [decision] sample_rate is dropped only for an explicit encoding=mp3, not for the default
The API rejects `sample_rate` when `encoding=mp3` as "not applicable". mp3 is also the default
when no encoding is sent, so `sample_rate` with no encoding may hit the same rejection.
What lost: widening the drop to cover the unset case, which would have been the defensive
choice. What was chosen: follow the interface contract literally and drop it only on an explicit
`encoding=mp3`. Reason: guessing at the default's behavior would bake an unverified assumption
into the client, and one authenticated request settles it for real. HANDOFF section 3.4 muddies
it further by recording `/v1/speak`'s documented defaults as mp3 **and** `sample_rate=24000`
together, which cannot both be applicable if the rejection is real.
Cost if wrong: one rejected request with a clear `err_code`, on a path nothing uses yet.
This is now the top item on the list of things the first API key settles.
Source: custom_components/deepgram_tts/api.py `_build_params` · docs/chapter-2-notes.md
Routes to: chapter 2 live verification, and the open questions list

### [decision] container=none falls through the extension chain instead of becoming the extension
The contract's fallback chain for the file extension is content type, then container, then
encoding, then mp3. Taken literally, `container=none` yields `extension="none"`, which is not a
format and would confuse Home Assistant's converter. What was chosen: skip `none` and fall
through to the encoding, because `none` means raw frames with no wrapper rather than a container
called none. A deliberate deviation from the literal contract, recorded here because a later
reader will otherwise see the code disagree with the spec and assume the code is wrong.
Source: custom_components/deepgram_tts/api.py `_extension_for` · docs/superpowers/interface-contract.md
Routes to: a contract revision, and chapter 6 where raw linear16 gets a WAV header

### [decision] A local markdown renderer, because this machine has none
HANDOFF section 8.4 records that there is no `markdown`, `mistune`, or `pandoc` on this machine,
so rendering a spec to the print-ready HTML review copy needed a script that did not exist.
Written as a stdlib-only renderer that copies the canonical template's style block, theme
toggle, and script byte for byte and fills only the title and the content region.
Left in the session scratchpad rather than committed here, on purpose: it is machine-level
tooling for every repo that writes a spec, not part of this integration, and this repo flips to
a public snapshot later. Its home is `~/Developer/gutils/templates/` next to the template it
reads, which is a two minute move whenever that is wanted.
Source: scratchpad `render_md.py` · docs/superpowers/interface-contract.html
Routes to: a gutils commit, and the open questions list

### [surprise] display_name is null for 61 of the 102 Aura voices, not missing
Expected: `metadata.display_name` present on every catalog entry, with a missing key as the rare
defensive case. Actual: the key is present with a **null value** on 49 `aura-2` entries plus all
12 legacy `aura` entries. 61 of 102.
Why it matters more than it looks: `"display_name" in metadata` passes, so the obvious guard
does nothing and `None` lands in the voice picker. Every one of the 36 Flux voices has a real
display name, so testing only the Flux path finds nothing wrong. The fallback to a title-cased
`name` is the **normal** path for most of the Aura list, not an edge case, which changes what a
good picker label looks like and which voices are worth testing.
Fixed by treating null, empty, and whitespace as absent rather than checking for the key.
Source: custom_components/deepgram_tts/catalog.py `_optional_string` · live `/v1/models`
Routes to: chapter 4's picker labels, chapter 5's Voice list, technical blog post

### [claim] 138 voices merge with zero key collisions, and seven languages come out
Live run of the real parser over the real payloads: 138 merged voices, zero collisions on
`canonical_name`, and `supported_languages` of `de, en, es, fr, it, ja, nl`. Base codes only,
no `en-US` leaking in. With no preference, English resolves to `flux-haley-en` and the six
non-English bases resolve to `aura-2-agustina-es`, `aura-2-aurelia-de`, `aura-2-agathe-fr`,
`aura-2-beatrix-nl`, `aura-2-cesare-it`, and `aura-2-ama-ja`.
It held. Settled decision 4 is now demonstrated against the live catalog and not only in tests:
no non-English language can reach a Flux voice, because there is no Flux voice that claims one.
Source: chapter 3 agent's live parser run · tests/test_catalog.py, the six-language parametrize
Routes to: technical blog post, user-facing post, the language section of both

### [decision] resolve_voice grew a last resort, guarded on the language and not on the family
The contract's ladder was: the preferred voice, then the default for English, then the first
Aura voice for that language. That returns `None` for an English pipeline in the case where the
catalog has no Aura English voice, despite 36 usable Flux voices sitting right there.
Added a final step: the first voice of any family, **guarded on the base language code being
English**. The guard is on the language, deliberately, not on the voice's family. If Deepgram
ever ships a Flux voice mislabeled with a non-English language, a family-guarded fallback would
hand it to a Spanish pipeline and a language-guarded one will not. Settled decision 4 survives
a catalog that is wrong about itself.
Source: custom_components/deepgram_tts/catalog.py `resolve_voice`
Routes to: a contract revision, technical blog post

### [surprise] /v1/models is 183 KB and 445 of its entries are models we discard
Both catalogs are fetched at every config entry setup. `/v2/models` is 22 KB. `/v1/models` is
183 KB, of which 445 entries are `stt` models this integration throws away to get at 102 `tts`
entries. 205 KB per setup, with `TIMEOUT_CATALOG` at 15 seconds.
Not a problem on a laptop. Untested on a Raspberry Pi on wifi, which is the target hardware, and
a setup that times out is a `ConfigEntryNotReady` retry loop rather than a clean failure. Worth
measuring on the real instance before deciding whether it needs a cache.
Noted rather than fixed: adding a cache before measuring would be guessing, and the fix if it is
needed is small.
Source: docs/chapter-3-notes.md · live payload sizes
Routes to: the real-hardware checklist, and chapter 7 if the measurement says so

### [decision] Chapter 6 gets built on a branch and is not merged, because the trap is real
HANDOFF section 6 gates chapter 6 on chapter 5 running on real hardware. That gate cannot be
satisfied today: no API key, no access to the instance, and no speaker in the house.
The gate is not procedural. From section 2.1: `async_supports_streaming_input()` auto-detects
streaming by comparing `self.__class__.async_stream_tts_audio` against the base method, so
**defining the method is the opt-in and there is no flag.** The moment it exists, every Assist
pipeline response routes down it while direct `tts.speak` calls keep working. An unverified
streaming path does not sit inert next to a working batch path, it replaces it for the exact use
case this integration exists for, and only in the place nobody tests by hand.
So: main stops at chapter 5 and stays deployable. Chapter 6 is built fully, on its own branch,
with `stream.py` unit tested against a mocked socket, and merged after
`scripts/measure_first_frame.py` has produced a number on real hardware. Chapter 5's test suite
asserts `async_supports_streaming_input()` is False, so that assertion failing is the signal
that chapter 6 arrived and the merge is a deliberate act.
Source: HANDOFF.md section 2.1 · tests/test_tts.py, the streaming guard assertion
Routes to: technical blog post, and this is probably the post's strongest single section

### [decision] The WAV header's sample rate is an assertion, so the client checks its own math
The Flux socket emits raw `linear16` with no container, and nothing in the protocol tells the
client what rate those samples are at. `Connected` carries the model name and uuids, not a
format. So the 44 byte WAV header prepended to the stream declares a rate that the code
believes rather than a rate it was told.
What lost: inferring the rate, or trusting a documented default. Either is a guess, and a guess
that is wrong by a factor of two produces audio that plays at the wrong pitch. **Wrong-pitch
audio sounds like a bad voice, not like a bug**, so it would get blamed on Deepgram's voice
quality and never traced to a header.
What was chosen: pin the format in the socket query string, `encoding=linear16` and an explicit
`sample_rate`, so the request and the header agree by construction. Then check it at runtime:
bytes received against the `audio_duration_ms` that `SpeechMetadata` reports. A mismatch outside
ten percent logs the rate the stream actually implies.
Deliberately a warning and not an error. Audio at the wrong pitch still beats silence out of a
speaker in somebody's kitchen.
Source: custom_components/deepgram_tts/stream.py `_check_sample_rate` · tests/test_stream.py::test_sample_rate_mismatch_warns_and_does_not_raise
Routes to: technical blog post, and the first live socket run confirms or kills it

### [decision] A streaming WAV declares an unknown length, which is the whole point
A RIFF header carries two byte counts, and a stream does not know either of them until it ends.
What lost: buffering the audio to compute the real sizes, which is the one thing streaming
exists to avoid, and would have made chapter 6 a slower version of chapter 5.
What was chosen: the all-ones sentinel in both fields. ffmpeg, which is what Home Assistant
converts with in `_async_convert_audio`, reads to end of stream when it sees that.
Unverified: whether every playback path Home Assistant can hand this to is as tolerant as
ffmpeg. A media player that insists on a real length would reject the clip. That is a hardware
question and it is in the bill of materials for a reason.
Source: custom_components/deepgram_tts/stream.py `wav_header` · tests/test_stream.py::test_wav_header_declares_unknown_length
Routes to: the real-hardware checklist, technical blog post

### [friction] The socket's own error was replaced by the cleanup's CancelledError
Symptom: three tests that assert a specific failure got `asyncio.exceptions.CancelledError`
raised from a bare `yield` inside `asyncio.sleep`, with no mention of the socket anywhere in the
traceback. The real failure had vanished.
Cause: when the receive loop raises, the `finally` cancels the sender task and awaits it. The
handler caught `Exception`, and `CancelledError` derives from `BaseException`, so it went
straight through and replaced the error that actually mattered.
Fix: catch `CancelledError` explicitly and swallow it **only when `sender.cancelled()` is true**,
meaning we are the ones who cancelled it. If the task is not cancelled, the cancellation came
from outside and swallowing it would make the whole coroutine uncancellable.
Worth writing down because the naive fix, suppressing `CancelledError` outright, passes every
test in this file and quietly breaks shutdown.
Source: custom_components/deepgram_tts/stream.py `_finish_sender`
Routes to: technical blog post, and a gotchas post about async cleanup

### [claim] The fake socket proves the interleaving, which a fixed message script cannot
The test double answers `Speak` with audio and `Flush` with `SpeechMetadata`, as a state machine
rather than a fixed list of messages. That choice is the test.
A fixed script passes even for an implementation that sends every chunk before reading anything,
which is exactly the implementation that deletes the benefit of streaming while looking correct.
The state machine makes `test_audio_arrives_before_the_text_runs_out` meaningful: it asserts the
first audio frame is yielded while fewer than five of five chunks have been sent.
It held. 17 socket tests, 62 in the suite.
Source: tests/test_stream.py · `.venv/bin/pytest -q` → `62 passed in 0.46s`
Routes to: technical blog post, the testing section

### [surprise] A custom integration's Python cannot be reloaded in place, and that sets the whole loop
Expected: `homeassistant.reload_config_entry` to pick up an edited `.py` file, the way a
development server would.
Actual: `sys.modules` caches the import, so reload re-runs `async_unload_entry` and
`async_setup_entry` against the module Home Assistant **already loaded**. It is genuinely
useful for a changed option, a retried catalog fetch, or a replaced API key. It does nothing at
all for a code edit, a new module, `manifest.json`, `strings.json`, or a new requirement.
So every code iteration costs one full Home Assistant restart. That is the argument for making
the copy step instant rather than elegant, and it is why the recommendation is rsync over ssh
for chapters 5 and 6, with HACS used exactly twice: once at the end of chapter 7 to prove the
distribution path on a clean instance, and once after the flip to public.
The second reason matters more than loop speed: Studio Code Server and Samba both tempt you into
editing on the far side, and then the fix that made it work lives on the Pi instead of in a
commit. Expensive here specifically, because the lab convention rewrites this history into build
order later and a fix that never reached git cannot be rewritten into anything.
Source: docs/deploy-notes.md · docs/deploying.html
Routes to: the real-hardware checklist, technical blog post

### [surprise] Home Assistant renamed add-ons to apps in 2026.2
Every tutorial, forum answer, and doc page written before February 2026 calls them add-ons. The
panel was refactored into the frontend and old `/hassio/addon/...` URLs may break. The Samba
app's shares were renamed with them: `addons` became `local_apps` and `addon_configs` became
`app_configs`, both still working.
Worth recording because it makes almost every existing deployment guide subtly wrong, which is
exactly the kind of thing worth a paragraph in a post. Also: Studio Code Server is aarch64 and
amd64 only, so a 32 bit armv7 Pi cannot run it at all.
Source: docs/deploy-notes.md · researched live 2026-09-15
Routes to: user-facing blog post, the install section

### [friction] The log tailer looped forever on a failed fetch in one-shot mode
Symptom: `tail_ha_log.sh` with follow disabled and an unreachable instance never returned.
Cause: the failure branch called `continue` before the follow check, so a one-shot run behaved
like a follow run that could never succeed.
Fix: a failed one-shot fetch now exits 1 with a message naming both variables to check. Found by
actually running the failure paths against a stub server on localhost rather than by reading the
script, which is the only reason it was found at all.
Source: scripts/tail_ha_log.sh
Routes to: nothing outside the repo, but it is a good example for the testing section of a post

### [decision] shellcheck could not run, and that is recorded rather than glossed
`shellcheck` is not installed on this machine and there is no Docker daemon to run it in a
container, so `scripts/deploy.sh` and `scripts/tail_ha_log.sh` have `bash -n` plus real
execution of every failure path behind them, and no static analysis pass.
Nothing was installed to fix it. The scripts were written defensively for it instead: quoted
expansions throughout, rsync arguments built as an array, and two targeted disable comments.
Open item before the flip to public, because a public repo's shell scripts get read.
Also worth knowing: the brief asked for POSIX plus `set -o pipefail`, and those are mutually
exclusive. `pipefail` and arrays won; the shebang is `#!/usr/bin/env bash` and each script says
so in its header.
Source: docs/deploy-notes.md · `shellcheck not found`
Routes to: chapter 7, and the pre-flip checklist

### [surprise] The null display_name fallback collides on live data, not in theory
The chapter 3 finding was that `metadata.display_name` is null on 61 of 102 Aura voices, so the
title-cased bare `name` fallback is the normal path. Chapter 4 found the consequence: **the
fallback is not unique.** Legacy `aura-asteria-en` and current `aura-2-asteria-en` both fall back
to "Asteria", same family, same accent, so a label of name plus family plus accent shows a user
two identical options.
Not a hypothetical. Both voices are in the live `/v1/models` payload right now.
Fix: the label carries the voice id, `Asteria (Aura, Neutral) [aura-2-asteria-en]`. The id is the
catalog's own key so it always disambiguates, and it is also the model string the request sends,
which is the thing a reader comparing this to Deepgram's docs actually wants to see. A test
appends the legacy entry and asserts the two labels differ, that all 138 are unique, and that no
label contains the string None.
The general lesson, which is the part worth writing up: a fallback that is good enough to display
is not automatically good enough to identify.
Source: custom_components/deepgram_tts/config_flow.py · tests/test_config_flow.py::test_aura_fallback_label_is_usable_and_unique
Routes to: technical blog post, and this is a strong standalone section

### [decision] 138 voices in one dropdown, no language step, and sort explicitly off
What lost: a language step before the voice picker, which would cut 138 options to a handful.
What was chosen: one flat dropdown, all 138, ordered Flux first then English Aura then the rest
grouped by base language.
Three reasons, in order of weight. The configured voice is a **preference, not a constraint**:
`resolve_voice` already refuses to send a Flux voice down a non-English pipeline and picks per
request, so filtering the picker by language would filter on something the entity does not treat
as binding. Home Assistant renders a dropdown select as a type-to-filter combo box, so "haley"
or "-es" narrows it with zero extra clicks. And only 49 of 138 voices are non-English, so a
language step taxes the common case to organize the rare one.
`sort=False` is written out explicitly even though it is already the default, because frontend
sorting would alphabetize the labels and silently destroy the Flux-first ordering the whole
design rests on. That is the kind of default that changes in a minor release.
Unverified and worth checking on the real instance: whether the frontend really renders 138
options as a type-to-filter combo box. If it renders a flat 138 row list, this decision should
be revisited, and it is a one step change.
Source: custom_components/deepgram_tts/config_flow.py · docs/chapter-4-notes.md
Routes to: the real-hardware checklist, user-facing blog post

### [decision] The voice lives in options only, never in entry data
Unspecified by the interface contract, which says the entry title is the voice and that options
include the voice, without saying where the initial pick lands. `entry.data` holds only the API
key. `entry.options` holds only the voice, with no seeded speed, so chapter 5 has to read speed
as `options.get(CONF_SPEED, DEFAULT_SPEED)` and must not read `entry.data[CONF_VOICE]`.
Recorded because a later chapter reading the wrong dict gets `None` and a confusing failure
rather than an error.
Related: speed visibility is driven by the voice **currently stored in options**, not the one
being picked in the same form, because a form's schema is fixed before the user touches it.
Switching Flux to Aura saves the voice, drops the stored speed, and reloads, and the next visit
shows the right fields.
Source: custom_components/deepgram_tts/config_flow.py · docs/chapter-4-notes.md
Routes to: a contract revision, chapter 5

### [friction] The entity ids were exactly right and every synthesis failed
Symptom: chapter 1's naming assertions passed, the registry showed `tts.deepgram_flux_haley` and
`tts.deepgram_aura_celeste` as intended, and then every call raised
`HomeAssistantError("TTS engine name is not set.")` from `_async_generate_tts_audio`.
Cause: chapter 1 set `_attr_has_entity_name = True` with `_attr_name = None`. That combination
produces the entity id from the device name, which is why the ids looked correct, while
`entity.name` stays `None`, and the tts manager refuses to synthesize without it. **The entity id
and `entity.name` come from different places**, so a registry that reads correctly tells you
nothing about whether the service works.
Fix: `_attr_name = entry.title` plus `DeviceInfo(name=entry.title)`, which is what core's
`google_cloud` TTS entity does. Both original entity ids still hold.
This is the same shape as the streaming auto-detection trap in HANDOFF section 2.1: a failure
only the calling path surfaces, invisible to anything that inspects state. Chapter 1's tests
asserted on entity ids, which is exactly the check that cannot see it. Two of these in one
project is a pattern, not a coincidence, and it is the most useful thing this build has to say
to anyone writing a Home Assistant TTS entity.
Source: custom_components/deepgram_tts/tts.py · docs/chapter-5-notes.md
Routes to: technical blog post, and this is the strongest single section in it

### [claim] HANDOFF section 2.1's headline verdict does not hold, and I checked it myself
The handoff says `async_timeout` "is not in HA core requirements" and "nothing installs it, so
the integration almost certainly did not load at all." That claim was going to be the opening
line of a blog post.
It is wrong. `ha-ffmpeg==3.2.2` requires `async-timeout` with **no environment marker**, while
`aiohttp==3.14.3` and `bleak==3.0.2` both guard it behind `python_version < "3.11"`.
`homeassistant/components/tts/manifest.json` declares `dependencies: ["http", "ffmpeg"]`, and
`ffmpeg` requires `ha-ffmpeg`. So `async_timeout` is importable on every instance a TTS
integration runs on, and it is present in this project's own test venv at 5.0.1.
Found by the content agent while building the fact sheet, then re-verified here independently by
enumerating `importlib.metadata.requires` across every installed distribution and reading the two
manifests. Both runs agree.
**The pydub half stands and is the real cause**, which makes the actual bug better than the one
we thought we had: the integration loaded, direct `tts.speak` calls worked, and only the Assist
pipeline failed. It looked healthy to anyone testing by hand.
The transferable lesson is not the one we started with either. It is not "declare your imports or
nothing installs them." It is that **an undeclared import which happens to resolve through
somebody else's transitive dependency is worse than one that fails outright**, because it works
until that dependency drops the marker, and then it breaks for reasons nobody can trace.
Source: docs/handoff-corrections.md C1 · `.venv/bin/python` over importlib.metadata · installed tts and ffmpeg manifests
Routes to: technical blog post, and it changes the opening

### [claim] /v2/speak validates unknown fields before auth but not value ranges, and that half of section 3 was never probed
HANDOFF section 3 says its parameter table was "enumerated by sending deliberately invalid values
and reading the rejections," which is how `encoding` and `container` were established. Applied to
`speed`, it does not work: `speed=3.0`, `speed=0.1`, and `speed=1.07` all return
`401 INVALID_AUTH`, not 400.
So the documented 0.5 to 1.5 range in 0.05 increments is from Deepgram's docs and is unverified.
What does run pre-auth, confirmed with controls in the same batch: an unknown query parameter
returns `400 INVALID_QUERY_PARAMETER`, and an Aura model on `/v2/speak` returns
`400 V1_MODEL_ON_V2_SPEAK_ENDPOINT`. Schema shape is checked before credentials; parameter values
are not.
It held in the sense that matters: the two-endpoints finding the entire client design rests on is
pre-auth and therefore genuinely probed. Only the numeric ranges were docs-sourced and presented
as probed.
`const.py`'s comment claimed the endpoint validates the range. Corrected to say where the range
came from. Added to the first-API-key list: send `speed=1.37`, off the 0.05 grid, and record
whether it is rejected or silently rounded, because the options-flow slider step depends on it.
Source: docs/handoff-corrections.md C2 · six live requests with a dummy token, run twice by two sessions
Routes to: technical blog post, the "probing an API before auth" section

### [decision] ATTR_AUDIO_OUTPUT is advertised by nobody here, against the contract
The interface contract told chapter 5 to advertise `ATTR_AUDIO_OUTPUT` in `supported_options`.
It is not advertised, deliberately.
Reason: it is free-form per integration, absent from HA's `_PREFFERED_FORMAT_OPTIONS`, never read
by `_async_generate_tts_audio`, and the only two core consumers give it incompatible meanings.
`cloud` uses `mp3` and `raw` and puts it in `default_options`; `wyoming` advertises it and ignores
it. Advertising an option without honoring it lets a caller pass something that silently does
nothing, which is worse than not offering it.
Honoring it would be worse still: HA compares the returned extension against `preferred_format`
only, so `audio_output: wav` with no `preferred_format` would produce WAV and then transcode it
straight back to mp3. Two format knobs that disagree.
Shipped: `[ATTR_VOICE, ATTR_PREFERRED_FORMAT, CONF_SPEED]`. Chapter 6 must not add it back
without a defined value set.
Source: custom_components/deepgram_tts/tts.py · docs/chapter-5-notes.md
Routes to: a contract revision, and a gotchas post about the TTS options contract

### [surprise] tts.speak never synthesizes anything, so a silent speaker is not evidence
Expected: calling the `tts.speak` service to produce audio.
Actual: it hands the media player a `media-source://tts/...` URL and returns. Synthesis happens
only when something fetches that stream.
Matters on real hardware more than in tests: a `tts.speak` call that returns cleanly and a
speaker that stays silent is a **playback** problem, not a synthesis problem, and the natural
next move of adding logging to the synthesis path is a wasted hour. Check whether the stream was
fetched before checking whether it was generated.
Related trap found the same way: HA's tts manager memory-caches on message plus language plus
options plus engine, so two calls with the same message in one test replay the first result and
never reach the entity. An API assertion after the second call passes against a stale call. Every
chapter 5 test passes `cache=False` and a distinct message.
Source: docs/chapter-5-notes.md · tests/test_tts.py
Routes to: the real-hardware checklist, technical blog post, gotchas post

### [asset] Twelve ELI5 diagrams and three animated SVGs
`docs/eli5-ha-flux-tts.html` plus `docs/assets/streaming-vs-batch.svg`,
`flush-boundaries.svg`, and `voice-resolution.svg`. Every stroke is a template CSS variable or
`currentColor`, so all fifteen survive dark mode and print, and nothing carries meaning by color
alone.
The three animations exist because their subjects are about time. A still picture of streaming
against batch shows two architectures; a shared time axis with a playhead shows why one of them
is the point.
Every voice id on the page was confirmed present in the live catalogs. The two time-axis diagrams
use illustrative spacing, stated on the page, because no latency has been measured.
Source: docs/eli5-ha-flux-tts.html · docs/assets/
Routes to: both blog posts, video B-roll, the hub

### [claim] The trap fired in our own test suite, which is better evidence than the audit
Adding `async_stream_tts_audio` on the chapter 6 branch broke **15 tests that had nothing to do
with streaming.** Thirteen of them drove `async_get_media_source_audio`, which is how Home
Assistant itself synthesizes, so the moment the method existed the manager routed all of them
down the websocket. They were written as batch tests and had silently become fallback tests.
That is HANDOFF section 2.1 reproduced exactly, in this project, by us, two hours after writing
it down as a thing to avoid. In a test suite it shows up as 15 red tests. In a house it shows up
as a voice assistant that stops working while `tts.speak` keeps passing, which is why the
community integration looked healthy to anyone who tested it by hand.
It held, and it is stronger evidence than the audit was. The audit said "this can happen to
you." This says "it happened to us, with the warning open in another window."
Fix: the batch tests call `async_get_tts_audio` by name. Chapter 5's guard assertion was
**inverted rather than deleted**, because the fact it pins has not changed: if that method is
ever removed or renamed, streaming turns off silently and every pipeline reverts to batch with
nothing failing.
Source: tests/test_tts.py header · docs/chapter-6-notes.md · commit 254f310 on chapter-6-streaming
Routes to: technical blog post, and it is now the strongest section in it

### [decision] Two failure windows, and only one of them can fall back
Settled decision 5 says a dropped socket degrades to batch rather than erroring. Building it
turned up that this is only true before anything has been yielded, and the handoff does not
distinguish the cases.
Before the first audio frame reaches the caller: serve the whole turn from `/v2/speak`. A
listener hears no difference.
After: a batch clip cannot be appended. It arrives with its own 44 byte RIFF header, which lands
in the middle of the stream and decodes as the first half followed by garbage. So the turn ends
where it ends and the log says why. **Truncated speech is bad; a second WAV header mid-stream is
worse**, because it fails in a way nobody can diagnose by listening.
To keep the safe window as wide as possible the entity **holds the socket's WAV header** until
the first real audio frame arrives. A header already sent is what makes a clean fallback
impossible, so 44 bytes of delay buys the entire fallback window.
Confirmed independently from the other direction: `TTSCache.async_load_data` drains the generator
once in a background task and `async_stream_data` yields every already-buffered chunk before
re-raising, so a mid-turn fallback is exactly the concatenation described above. Two
investigations, one reasoning about RIFF headers and one reading HA's cache, same hazard.
Source: custom_components/deepgram_tts/tts.py `_socket_stream` · docs/handoff-corrections.md C6
Routes to: technical blog post, chapter 6 section

### [claim] The unknown-length WAV header is readable, and real ffmpeg proves it
`stream.py` writes `0xFFFFFFFF` into both RIFF size fields because a stream cannot know its own
length. Nothing downstream had ever been asked whether that is acceptable.
It is. Two independent checks. `test_the_streaming_wav_survives_home_assistants_own_ffmpeg_pass`
asks the tts manager for mp3 while the entity produces wav, which forces `_async_convert_audio`
to shell out to the real ffmpeg on this machine, and it converts cleanly. Separately, HA's exact
command line was replayed over a non-seekable pipe against all five variants of the size fields,
including wyoming's zeros: byte-identical output, nothing truncated, and conversion is
progressive rather than buffered to end of stream.
Better than expected: `_async_convert_audio` carries a special case that exists for precisely
this, `-probesize 32` when the input is a generator and the extension is wav, with a comment
saying it is to minimize probing latency for live TTS audio.
Still open, and it is a hardware question: whether a **playback device** is as tolerant as
ffmpeg. The hardware research found a HEAD handler in core whose comment says it exists for
Samsung DLNA renderers, which is a map of which devices break on a stream with no
Content-Length.
Source: tests/test_tts_streaming.py · docs/ha-2026.9-verification.md · docs/handoff-corrections.md C5
Routes to: technical blog post, the real-hardware checklist

### [surprise] Streamed audio is never cached, and the socket opens whether or not anyone listens
Two facts from reading HA's TTS cache that nobody would guess and that change what this costs.
The generator drain starts the moment Home Assistant creates the result stream, not when a
player fetches it. So the socket opens and Deepgram bills the characters even if nothing ever
plays the audio.
And streamed audio is never cached or deduplicated: `store_to_disk=False`, keyed on a ULID.
Batch audio **is** cached. So switching a house from batch to streaming turns every repeated
question into a fresh billed request. At $0.045 per 1,000 characters that is a real difference
for a household that asks the same thing every morning.
Related and load-bearing for the measurement: `tts.speak` defaults to `cache: true`, which makes
the cache the single biggest threat to the first-frame number. A second call measures the cache,
not the API. Every measurement passes `cache: false`.
Source: docs/ha-2026.9-verification.md · docs/hardware-notes.md
Routes to: technical blog post, the cost section, and the measurement protocol

### [claim] Returning WAV is correct but not free, and the handoff says free
HANDOFF section 4.3: "returning WAV and letting HA transcode is correct and free."
Correct, yes, and it is the core-normal choice: two of the three core integrations that stream
also return wav, and the reference implementation for our shape is `wyoming` rather than
`elevenlabs`. Free, no. `final_extension` falls back to `_DEFAULT_FORMAT`, which is mp3, so
ffmpeg runs on essentially every call, and Assist forces it unconditionally by setting a
preferred sample rate alongside the format.
Did not hold. **Any latency budget taken from the handoff is short by one ffmpeg subprocess
spawn per turn**, which on a Raspberry Pi is not nothing. It has to be inside the first-frame
measurement rather than discovered after it.
The design does not change, because transcoding ourselves is still worse. Only the arithmetic
does.
Source: docs/handoff-corrections.md C5 · installed tts/__init__.py:1068-1070 and 1151-1157
Routes to: technical blog post, and the measurement protocol

### [decision] Correction to two earlier entries in this file
Append-only means corrections are new entries, so here are two.
**On stream.py's location.** The chapter 6 entry above says the socket client "is built fully,
on its own branch." It is not: `stream.py` landed on `main` as commit `dc0ac84`, inert, and only
the entity override lives on the `chapter-6-streaming` branch. The hold itself is intact and for
the stated reason, because the override is the only opt-in, and putting the engine on main was
deliberate: it makes chapter 6 a small reviewable diff that only wires it up, which is the right
size for the one change in this project that goes live the moment it exists.
**On test counts.** The entry claiming "62 tests" was true when written and is now stale. Main is
at 99. The `chapter-6-streaming` branch is at 108. Any number quoted in content should be read
off the suite at the time of writing, not out of this file.
Source: `git log --oneline` · `.venv/bin/pytest -q`
Routes to: nothing outside this file, but it is why a ledger needs a correction rule

### [asset] The hardware bill of materials, which was the gap nobody had researched
`docs/hardware-bom.html`, print-ready, three tiers priced and dated 2026-09-15, plus
`docs/hardware-notes.md` with every fact weighted source, weak, or inferred.
Bench $12.50. One room hands free $58.95, a single Voice Preview Edition, one line item because
padding it would have been dishonest. Two rooms on camera $163.14.
The finding that changed the recommendation: **`rhasspy/wyoming-satellite` is archived and read
only**, last push 2026-01-24, 212 open issues abandoned, and every "build a Pi voice satellite"
tutorial on the internet still points at it. Its replacement speaks the ESPHome protocol rather
than Wyoming and calls itself experimental. That deleted the Raspberry Pi tier outright.
The finding that vindicated a settled decision nobody had a hardware reason for: an ESPHome
satellite advertising the speaker flag **hard-refuses anything that is not WAV**, with "Only WAV
audio can be streamed." Settled decision 6 was right for a reason that was not known when it was
settled.
Source: docs/hardware-bom.html · docs/hardware-notes.md
Routes to: the buy list, user-facing blog post, video B-roll planning

### [claim] We shipped the exact bug we founded the project on avoiding, and a review caught it
HANDOFF section 2.2's first and heaviest do-not-repeat: do not let a broad handler turn your own
auth error into something else, because a caller cannot then tell an expired key from a dead
network. Every error path in `api.py` was built to honor that, and `api.py` came out of the
skeptic review as the strongest file in the repo.
And then `stream.py` did it anyway, on the primary path. A rejected key fails the **HTTP
upgrade**, so it never produces an in-band `Error` frame. It arrives as
`WSServerHandshakeError`, which is a `ClientError` subclass, so the generic handler turned it
into `DeepgramConnectionError`. The test that looked like it covered this,
`test_auth_shaped_server_error_raises_auth_error`, exercises an in-band error frame, which a
real expired key almost certainly never sends.
Worse on the chapter 6 branch than on main: the fallback catches exactly that class, so an
expired key would have quietly retried the same dead key against `/v2/speak`, failed again, and
reported whichever error came second. The cause hidden twice.
Did not hold, and the interesting part is why. The rule was written down, understood, honored
everywhere it was being thought about, and broken in the one place where the auth failure
arrives through a transport nobody was picturing. **Knowing the rule is not the same as knowing
where it applies**, and the only thing that closed the gap was somebody adversarially reading
code they did not write.
Fixed: handled ahead of `ClientError`, parametrized over 401 and 403, and `DeepgramAuthError`
now propagates past the streaming fallback on purpose.
Source: custom_components/deepgram_tts/stream.py · tests/test_stream.py::test_a_rejected_key_on_the_handshake_is_an_auth_error · docs/review/skeptic-pass-2026-09-15.md finding 1
Routes to: technical blog post, and it is the honest ending the post needed

### [claim] Two things with ledger entries behind them had no test, and deleting them stayed green
Mutation testing planted 15 defects and the suite caught 13. The two it missed both had prose in
this file explaining why they mattered.
**Deleting the family guard from `resolve_voice` passed all 62 tests.** The six-language
parametrize looked like it covered settled decision 4, and did not: its fixture gave each
language exactly one voice and that voice was Aura, so "first non-Flux candidate" and "first
candidate" were the same object. The guard could be removed without anything failing.
**Deleting `await self._finish_sender(sender)` entirely passed all 62 tests.** Sixteen lines with
a whole ledger entry behind them and zero coverage. `FakeSocket.closed` was tracked and never
asserted.
Both now have tests that fail when the code is removed. The transferable lesson, which is
sharper than "write more tests": **a test whose fixture makes two different behaviors produce
the same answer is not a test, and reads exactly like one.** The only way we found out was
deleting the code and watching nothing break.
Source: docs/review/skeptic-pass-2026-09-15.md findings 3 and 4 · tests/test_catalog.py::test_the_family_guard_is_load_bearing_for_every_language
Routes to: technical blog post, the testing section, and a standalone post on mutation testing

### [friction] ruff's own formatter emitted syntax that would have crashed CI
Symptom: the CI `lint` job runs `python3 scripts/manifest_check.py`, which parses the integration
with `ast`, and it would have crashed on the runner rather than reporting anything.
Cause: `pyproject.toml` sets `target-version = "py314"`, so `ruff format` rewrote a
parenthesized `except (DeepgramAuthError, DeepgramConnectionError):` into PEP 758's
unparenthesized form. That is a `SyntaxError` on anything older than 3.14, and the job had no
`setup-python` step, so it would have run on the runner's system interpreter.
Fix: pin 3.14 in the lint job. The syntax is correct for this project and the formatter was
right; the job was wrong about which interpreter it needed.
Worth recording because the guard against undeclared imports is the one CI check this project
most depends on, and it would have been silently broken on the very first push. Confirmed
locally: `/usr/bin/python3` is 3.9.6 and cannot parse `stream.py`.
Source: .github/workflows/validate.yml · docs/review/skeptic-pass-2026-09-15.md finding 6
Routes to: technical blog post, a gotchas post about target-version

### [decision] The chapter 6 merge gate does not test what it gates, and that is recorded not fixed
`scripts/measure_first_frame.py` was written as the gate: produce a first-frame number on the
real instance, then chapter 6 may merge. The review pointed out that the script **never imports
`stream.py`.** It opens its own socket and talks to Deepgram directly, and its
`degraded_cleanly` check exercises the batch endpoint rather than the entity's fallback.
So satisfying the gate as written would produce a real, quotable latency number and would
validate none of the code the gate exists to protect.
Left unfixed on purpose, and the choice is worth stating. Rewriting the script to drive
`FluxSocket` would make it depend on a Home Assistant import graph, which is the reason it is
stdlib plus aiohttp and runnable on a bare Pi in one command. The better answer is a second gate
step that runs on the instance with the branch deployed, which cannot be written until there is
an instance to run it on.
**A gate that does not test what it gates is worse than no gate**, because it converts a real
check into a ritual. Written down so nobody mistakes the number for the verification.
Source: docs/review/skeptic-pass-2026-09-15.md finding 12 · docs/chapter-6-notes.md
Routes to: chapter 6's merge checklist, technical blog post

### [correction] Two more corrections to entries above
Append-only, so these are new entries rather than edits.
**"Settled decision 4 survives a catalog that is wrong about itself" was false when written.** The
entry described the last-resort branch's language guard accurately and then generalized it to the
whole function. The preferred-voice branch was guarded on neither language nor family and trusted
the catalog completely, and `resolve_voice(catalog, "es", "flux-rogue-es")` returned a Flux
voice. Reproduced, not theorized. It is true now, and the fix is one `elif`.
This one matters beyond the file: that sentence was headed for a blog post as a design win, and
it would have been a claim a reader could falsify in four lines.
**"17 socket tests" was 16.** The suite total of 62 was right. Current counts: main 120,
`chapter-6-streaming` 130.
Source: docs/review/skeptic-pass-2026-09-15.md · custom_components/deepgram_tts/catalog.py `resolve_voice`
Routes to: the blog draft, which needs that sentence rewritten before it goes anywhere
