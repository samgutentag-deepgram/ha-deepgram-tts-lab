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
