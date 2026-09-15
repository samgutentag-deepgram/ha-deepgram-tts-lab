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
