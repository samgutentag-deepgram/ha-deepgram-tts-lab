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
