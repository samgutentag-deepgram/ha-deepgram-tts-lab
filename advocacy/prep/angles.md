# angles.md, candidate story angles

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen and `advocacy-intake` has not run. Nothing here is a campaign claim. When
> intake does run, one of these becomes the frozen claim and the rest become later cycles.

Seven candidates. Each is three lines: the claim, who it is for, what evidence exists **today**.
Fact ids refer to `notes.md`.

---

**A1. Home Assistant decides your TTS entity streams by checking whether you overrode one
method, so writing a first draft of it puts it in front of every voice assistant response.**
For: anyone writing or maintaining a Home Assistant TTS integration.
Evidence today: `F2.1` (six lines of HA source read on disk), `F2.2`, `F2.3`, `F2.5` (the fork's
buffered generator at `FORK/tts.py:165-171`). Complete. Needs nothing measured.

**A2. An API that validates query parameters before it validates auth will hand you its own
schema if you send it deliberately wrong values.**
For: any developer integrating a REST API with thin docs, in any language.
Evidence today: `F6.1` to `F6.5`, five live responses quoting enums and legal value sets back.
Plus `F6.6`, the limit of the technique, which is the part that makes it credible.

**A3. Thirty six voices and every one of them English is an architecture constraint, not a
footnote in a release note.**
For: developers integrating a new TTS model family, and Home Assistant users outside English.
Evidence today: `F4.1` and `F4.2` (36 voices, English only, live), `F4.3` (102 Aura models
across seven languages, zero Flux entries), `F4.4`, `F4.5`. Complete.

**A4. Declaring your dependencies is not about whether your code runs today, it is about
whether it depends on a transitive dependency of a component you do not control.**
For: Home Assistant custom integration authors and HACS maintainers.
Evidence today: `F1.1` to `F1.9`, including the `tts` to `ffmpeg` to `ha-ffmpeg` to
`async-timeout` chain in `F1.5`, all verified live. `F1.6` kills the simpler version of this.

**A5. When the synthesis server places flush boundaries itself, your sentence splitter is dead
weight.**
For: anyone building streaming TTS into a voice agent.
Evidence today: thin. `F3.3` to `F3.5` are live facts about the fork's 206 lines, but `F3.1`
and `F3.2`, the protocol behavior the whole argument rests on, are `VENDOR` and untested.

**A6. Reading 858 lines to decide between repairing and restarting, and why the git history
was the deciding factor.**
For: engineers and tech leads who inherit a codebase and have to make this call.
Evidence today: `F8.1` (858 counted), `F8.2` (206 counted), `F8.4` (the three reasons, with
the GitHub fork-privacy constraint being the one nobody expects), `F8.5`. `F8.3` is an
estimate and has to be labeled as one.

**A7. Deepgram Flux TTS is available for your Home Assistant voice assistant. Install it and
pick a voice.**
For: Home Assistant users who will never read the code.
Evidence today: **none.** `F9.4` says the entity raises instead of synthesizing. This angle
describes a product that does not exist yet.

---

## Ranked

| # | Angle | Why here |
| --- | --- | --- |
| 1 | **A1, the streaming opt-in** | Fully verified from source, generalizes to every HA TTS integration, and it explains a failure shape (works from a script, breaks in the voice pipeline) that reads as unexplainable in a bug report. Nothing about it depends on this project succeeding. |
| 2 | A2, probing before auth | Live evidence, reusable against any API, and honest about its own limit. Reads as craft rather than as a product pitch. |
| 3 | A4, declared dependencies | The reversal is the value: the obvious version of this claim is wrong, and finding that out took five commands. Good for the same audience as A1. |
| 4 | A3, English-only voices | Real constraint, fully verified, explains an architecture decision. Ranks below A4 only because it is specific to this API rather than transferable. |
| 5 | A6, repair versus restart | Genuine and well evidenced, but it is a judgment-call essay. Interesting to fewer people, and the weakest number in the set (`F8.3`) sits inside it. |
| 6 | A5, flush boundaries | The best story in the project and currently unsupported. Do not write it yet. |
| 7 | A7, the user-facing pitch | Cannot be written. There is no product to install. |

**Top angle: A1.** It is the one a hyper-critical reader cannot poke a hole in, because the
evidence is six lines of Home Assistant's own source and a line range in a public repo.

## Currently unsupported by evidence

| Claim | What is missing | What would support it |
| --- | --- | --- |
| A5, the server handles segmentation so the splitter is unnecessary | `F3.1`, `F3.2`, `F11.4`. Nobody has opened the socket | One authenticated session logging the full message sequence for a multi-sentence turn, showing audio frames arriving between `SpeechStarted` and `SpeechMetadata` with no client-side splitting |
| A7, install it and pick a voice | `F9.4`, `F11.3`, `F11.6`. No synthesis, no hardware, no install | Chapters 2 to 5 landed, installed on the real instance, `tts.speak` producing audio, and a speaker to hear it on |
| "Flux is fast" in any wording | `F11.2`. No latency number exists on any hardware, and the vendor's 80 ms is a different measurement | First token to first audio frame, measured on the target hardware, across enough turns to quote a median and a spread, with the sample size in the sentence |
| "This replaces the community integration" | Nothing measured, and it is a claim about somebody else's users | Not a measurement problem. This claim should not be made at all |
| "Deleting 206 lines was the right call" | `F3.6`. The design bet is unresolved | Chapter 6 working on hardware, which retroactively makes `F3.6` a result instead of a plan |
| "Streaming lowers perceived latency for Assist" | No before and after exists | Same pipeline, same text, batch path versus socket path, timed on the same hardware |

Two notes on that table. First, "Flux is fast" is not an angle and will not become one by being
phrased more carefully; it becomes one when there is a number with a sample size behind it.
Second, every unsupported row is unblocked by the same two things: an API key and hardware.

---

## The editorial risk, named explicitly

**The single biggest editorial risk in this campaign is that a post about the audit reads as
dunking on a volunteer's open source project.**

`alceasan/ha-deepgram-tts` is one person's unpaid work. It shipped a working one-shot TTS path
against a real API, people installed it, and it is the reason this project knows the shape of
the problem before writing a line of code. The fact sheet holds roughly fifteen named defects
in it, each one true, each one cited to a line number. A post can be completely accurate and
still be a failure, and this is the way this campaign fails.

What makes it go wrong, concretely:

1. **Itemizing.** A list of dead functions, unused imports, and a duplicated definition reads
   as an inventory of somebody's mistakes. `F10.1` exists as a category in `notes.md` for
   exactly this reason, and stays a category in every draft.
2. **Counting.** "Fifteen defects in 858 lines" is a scoreboard. The counted numbers in `F8.1`
   and `F8.2` are for the repair-versus-restart argument, not for measuring a person.
3. **Leading with the breakage.** Opening a post with "this integration does not load" makes
   the volunteer's work the subject of the piece. `F1.6` means that framing is also probably
   false, which turns a tone problem into a correctness problem.
4. **Naming without crediting.** Every mention of the repo carries its name as prior art in
   the same breath as any finding. Never a finding first and attribution in a footnote.

The test that every sentence has to pass: **does the reader learn something they can apply to
their own code?** `F2.1` passes, because the streaming opt-in catches anyone who writes that
method. `F4.5` passes, because discovery against the wrong API version is a general failure
mode. "They left three unused exception classes in the file" fails, because the only thing the
reader learns is that somebody left unused classes in a file.

A second risk, smaller and worth writing down: **this is a Deepgram employee writing about a
Deepgram API replacing a community integration built on Deepgram's own older API.** The
conflict of interest is real, obvious to the Home Assistant community, and the only defense is
that every claim is checkable and every limit is stated first. A post that hedges the
limitations into a closing paragraph reads as marketing no matter how true it is.
