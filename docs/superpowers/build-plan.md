# Build plan: Deepgram Flux TTS for Home Assistant

Written 2026-09-15, during the first build session. Supersedes nothing; `HANDOFF.md` stays the
fact base and this is the plan laid over it.

Three tracks run at once: the integration, the hardware, and the content. They have different
blockers, and the useful thing this document does is say which is which, because the instinct
is to treat "the project is blocked" as one fact when it is three.

---

## 1. What is being built

A Home Assistant custom integration, domain `deepgram_tts`, that makes Deepgram Flux TTS the
voice of a Home Assistant voice assistant. Flux is the default. Aura-2 stays supported because
every Flux voice is English and Aura-2 is the only way to serve a non-English Assist pipeline.

Distribution is a HACS custom repository. The floor is Home Assistant 2026.9.0.

This is a fresh build, not a fork. `alceasan/ha-deepgram-tts` is credited as prior art and its
defects are a checklist of things not to repeat, recorded in `HANDOFF.md` section 2.2.

---

## 2. How this session was run, and why

The build order in `HANDOFF.md` section 6 is seven sequential chapters. Sequential is the right
shape for the public commit log, which is supposed to read as a tutorial. It is the wrong shape
for one afternoon.

So the chapters were split across agents in separate git worktrees, behind a contract written
first:

1. Chapter 1 was built by hand, including `const.py`, `errors.py`, and `models.py`, the three
   files every later chapter imports.
2. `docs/superpowers/interface-contract.md` froze every module boundary and signature, and
   assigned each file exactly one owner.
3. Chapters 2 and 3 ran in parallel, in their own worktrees, each with a list of files it owned
   and an instruction not to touch a file it did not own.
4. Chapters 4 and 5 ran in parallel once 2 and 3 merged, because both depend on the client and
   the catalog and neither depends on the other.
5. Research and content tracks ran alongside all of it, touching no shared files.

Merging is a fast-forward of new files rather than a conflict resolution, because ownership was
disjoint by construction. The contract is also the artifact that makes the sequential public
history possible later: the chapter boundaries are already written down.

**Each agent was asked to report anything in the contract that turned out wrong.** That was the
only defense against the obvious failure mode, which is an agent following a bad spec into a bad
design in silence. Four contract gaps came back, all recorded in `.hub/ledger.md`.

---

## 3. The integration track

| # | Chapter | State |
| --- | --- | --- |
| 1 | Scaffold | Landed. Entry loads, unloads, retries a dead catalog, two entries coexist |
| 2 | API client | Landed. One synthesize method, two endpoints, typed errors |
| 3 | Voice catalog | Landed. 138 voices merged, seven languages, no non-English Flux |
| 4 | Config flow | In progress |
| 5 | TTS entity, batch | In progress |
| 6 | TTS entity, streaming | Held on purpose. See below |
| 7 | Harden | Not started |

### Why chapter 6 is held, and why the hold is not procedural

`HANDOFF.md` section 6 gates chapter 6 on chapter 5 running on real hardware. That gate is
usually read as a nice-to-have. It is not, and the reason is section 2.1:

> `async_supports_streaming_input()` auto-detects by comparing
> `self.__class__.async_stream_tts_audio` against the base method.

**Defining the method is the opt-in. There is no flag.** The moment it exists, Home Assistant
routes every Assist pipeline response down it, while direct `tts.speak` calls keep working. An
unverified streaming path does not sit quietly beside a working batch path. It replaces it for
the exact use case this integration exists for, and only in the place nobody checks by hand.

That is precisely how the integration this project replaces shipped broken.

So: **main stops at chapter 5 and stays deployable.** Chapter 6 gets built in full on its own
branch, with the socket client unit tested against a mocked websocket, and it merges after
`scripts/measure_first_frame.py` has produced a number on real hardware. Chapter 5's test suite
asserts `async_supports_streaming_input()` is False, so that assertion failing is the signal
that chapter 6 has arrived and the merge is a deliberate act rather than a side effect.

### What the first API key settles

There is no `DEEPGRAM_API_KEY` on this machine, so nothing past Deepgram's auth check has ever
run. Three things are waiting on one environment variable:

1. `scripts/live_check.py`, the chapter 2 verification: one authenticated round trip against
   both `/v2/speak` and `/v1/speak`, audio written to disk.
2. Whether `sample_rate` is rejected when `encoding` is unset and therefore defaulting to mp3.
   The client currently drops it only for an explicit `encoding=mp3`. One request settles it.
3. `scripts/measure_first_frame.py`, which is the headline number for the whole campaign and
   cannot be faked.

The unauthenticated half is already verified. Both catalogs are public, and every count in
`HANDOFF.md` section 3.3 was re-fetched live and held.

---

## 4. The hardware track

This is the part `HANDOFF.md` never covered, and for Home Assistant it is the whole point:
integrating physical devices into a house. The gap matters because **there are currently zero
speaker devices and zero microphone devices in play.** A text-to-speech integration with nothing
to play audio out of is a unit test.

The bill of materials is `docs/hardware-bom.html`, researched in this session with current
prices and buy links. Read it there rather than having it summarized twice.

The thing worth saying in the plan rather than the BOM: **a cloud TTS integration can be made
pointless by the wrong playback device.** If the speaker buffers the whole clip before playing
it, streaming buys nothing, and the first-frame number that the entire streaming argument rests
on becomes unmeasurable end to end. So the hardware choice is not a shopping decision that
follows the software; it is a constraint on whether chapter 6 can be demonstrated at all.

Ordering hardware is the longest-lead item in the project and it is the first thing to do.

---

## 5. The content track

Two blogs, five canonicals, twenty variants, four videos, through four gates. That is
`advocacy-cycle`'s shape and it is not being short-circuited.

It cannot start yet, and the reason is worth stating plainly rather than treating as red tape.
`advocacy-intake` freezes the claim; `advocacy-cycle` refuses to run without a frozen one; and
`HANDOFF.md` section 8.5 gates intake on chapter 5 being on real hardware, because before that
there is nothing honest to claim. Nothing has made a sound yet.

What exists instead is `advocacy/prep/`: every fact with a citation, the candidate angles ranked
with their evidence named, two blog outlines, a full technical draft with every unverified claim
marked inline, the video slate, and four scripts written to the `script-to-video` style
contracts. Intake becomes a short job instead of a cold start.

**The strongest angle available today is not "Flux is fast."** No latency has been measured, so
that claim is unsupported and cannot be written. What is fully supported right now is the audit:
a two-line manifest omission that stopped an integration from loading, and a streaming
auto-detection trap that any Home Assistant TTS author can fall into. That is a real post, it is
true today, and it needs no hardware.

One editorial risk, named early because it gets worse the longer it goes unnamed: the audit
material is about a volunteer's open source project. A post that reads as dunking on it is a
failure even if every fact in it is accurate. The framing has to be that these are transferable
lessons, and the credit has to be real.

---

## 6. What is blocked on Sam

Short on purpose. Everything else has a path forward without him.

1. **A Deepgram API key in the environment.** Unblocks three things at once, listed in section 3.
2. **Order hardware.** Longest lead time in the project. `docs/hardware-bom.html` has the list.
3. **Three facts about the Home Assistant instance**: install type, hostname, and which add-ons
   are present. `docs/deploy-notes.md` has the exact questions. Thirty seconds to answer, an
   hour to guess wrong.
4. **A go-ahead on the Asana project**, which `project-hub init` creates as a team-visible
   project plus four tasks, one of which needs a check-back date only he can pick.
5. **Nothing on advocacy intake yet.** That waits on chapter 5 making a sound, not on a decision.

---

## 7. Sequencing from here

1. Merge chapters 4 and 5. Main is then a complete batch integration.
2. Deploy chapter 5 to the real instance and work the hand-check list in
   `docs/chapter-5-notes.md`. This is the gate everything else waits behind.
3. Run `scripts/live_check.py` and `scripts/measure_first_frame.py` on that hardware. The second
   one produces the campaign's only real number.
4. Merge chapter 6 once that number exists.
5. Chapter 7: README, CHANGELOG, first tag, HACS submission.
6. `advocacy-intake`, then `advocacy-cycle` from the staged material.
7. The flip: snapshot to a public repo with `.hub/` and `advocacy/` stripped from every commit.

Steps 1 and 5 are mechanical. Step 2 is the one that turns this from a design into a result.
