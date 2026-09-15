# notes.companion.md, what the facts mean

> **DRAFT. This file's parent has not been approved and does not exist yet.**
> No claim is frozen, `advocacy/advocacy.md` is unwritten, and `advocacy-intake` has not run.
> Staging only.

`notes.md` stays a clean fact list on purpose. Interpretation lives here, keyed to the same
fact ids, so a fact that is true and baffling six weeks from now can still be understood.

---

## Theme 1, the dependency story, is where the campaign nearly published something false

`F1.5` is the most valuable thing in the whole fact sheet and it arrived by accident, from
running `import async_timeout` inside the project's own test venv to confirm a claim everyone
had already accepted. It succeeded. Following the chain took four more commands and produced a
result that reverses the audit's headline verdict.

The chain matters more than the verdict. `tts` depends on `ffmpeg`, `ffmpeg` requires
`ha-ffmpeg`, and `ha-ffmpeg` asks for `async-timeout` with no environment marker while every
other package in the graph marks it `python_version < "3.11"` and contributes nothing on
Python 3.14. So the one package keeping the fork's undeclared import alive is a package pulled
in by the very component the fork is extending.

Why that is interesting rather than embarrassing: it is a better lesson than the one the audit
had. "Declare your requirements or your integration will not load" is easy to wave away,
because it clearly did load for the person who wrote it. "Declare your requirements, because
otherwise whether your integration loads depends on a transitive dependency of a component you
do not control, and nobody will tell you when that changes" is the actual rule, and it explains
why `scripts/manifest_check.py` exists in this repo (`F1.9`) instead of a code review note.

The editorial consequence is blunt: the two-line-bug framing is the most quotable thing in the
audit and it cannot be the lead of any piece. `F1.6` says so. Everything that survives from
Theme 1 is about pydub (`F1.3`, `F1.4`), where the failure is reproducible and the package is
genuinely absent from the environment.

## Theme 2 is the best transferable lesson in the project

`F2.1` is six lines of Home Assistant source and it is the thing a developer would actually
want to know. Streaming support is not a flag you set. It is inferred from whether your class
overrides one method, so the act of writing a first draft of `async_stream_tts_audio` routes
every Assist pipeline response through it. There is no state in between "not written" and
"live for the primary code path".

`F2.3` is why this reads as a mystery in a bug report rather than as an obvious breakage. A
user calls `tts.speak` from a script and it works. The same user talks to their voice
assistant and it fails. Nothing in the integration's own config distinguishes those two paths,
so the natural conclusion is that the voice pipeline is broken, not that the TTS integration
has two code paths and only one of them was finished.

`F2.5` is the other half. The fork has the streaming method, so HA routes to it, and the method
buffers the generator to completion before yielding. It satisfies the type signature exactly
and delivers none of the behavior the signature exists for. Worth being careful in the writing:
this is a subtle contract, the code is a reasonable first attempt at it, and the point is that
the contract is easy to satisfy on paper.

## Theme 3 is the design bet, and it is still a bet

`F3.2` is load bearing for the entire chapter 6 design. If the server does not place flush
boundaries the way HANDOFF says, then the 206 lines of `stream_processor.py` in `F3.3` are not
waste, they are a workaround for a real problem, and this project needs its own version of
them. Nobody here has opened the socket (`F11.4`).

So the honest framing of Theme 3 is a design argument, not a result: the protocol as
documented makes the segmentation layer unnecessary, and the build is structured on that
reading. A post that says "we deleted 206 lines because the server does the work" is claiming
a verified outcome. A post that says "the protocol as documented makes those 206 lines
unnecessary, and chapter 6 is where that gets tested" is claiming what is true today.

`F3.4` is the funniest thing in the audit and needs the most care in the telling.
`min_len = 2 ** count * 10` doubling per chunk to 10 MB by chunk 20 is a genuinely bad line,
and it is also harmless in the shipped code, because `F2.5` only ever sends one chunk. Two
defects canceling is worth one sentence about how defects hide each other. It is not worth a
paragraph at a volunteer's expense.

## Theme 4 is the constraint that shaped the product

`F4.4` is the single decision that makes this integration different from a model-string swap.
36 Flux voices and all of them English means a Flux-only integration silently takes German,
Spanish, French, Italian, Japanese, and Dutch users' voices away. That is why both families
ship, why routing is by model prefix, and why `supported_languages` is the union of two
catalogs rather than one.

`F4.5` is the kindest and most useful finding about the fork. Its voice discovery is not buggy.
It queries `/v1/models`, which returns 102 models and zero Flux entries (`F4.3`), so no amount
of correct code in that module could surface a Flux voice. The lesson generalizes past this
repo: when a vendor ships a new model family on a new API version, dynamic discovery against
the old version keeps working and keeps being wrong.

`F4.9` needs discipline. The permission question about `flux-marcus-en` and `flux-brittany-en`
is settled (`F4.8`) and does not appear in any draft. The engineering observation is real and
useful in exactly one place: a paragraph about why the shipped default is `flux-haley-en` and
what makes a voice a good default for a device that speaks in short bursts all day. Once, as
advice, never as a caveat about availability.

## Theme 6 is the most reusable trick in the whole project

Query-parameter validation running before auth means an unauthenticated probe returns the real
schema. `F6.2` and `F6.3` are the server handing over its own enums because it was asked for a
variant that does not exist. That is a technique a reader can use against any API, today,
which makes it a better paragraph than anything about this specific integration.

`F6.6` is the discipline check on that technique, and it is why the technique needs a caveat
rather than a victory lap. Send `speed=3.0` and you get 401, not a range error, because range
validation happens after auth. HANDOFF presents the 0.5 to 1.5 range as enumerated by probing,
and it was not. The method works for enums and rejects unknown fields; it does not see
anything validated later in the request lifecycle. Any table of "verified parameters" needs to
distinguish those two, which is what `F6.7` does.

## Theme 7 is the cost argument

`F7.1` plus `F7.4` is the concrete version of an abstract rule. Home Assistant already runs
ffmpeg for you when the requested format differs from what you returned, so an integration
that transcodes internally has bought a second transcode. The fork does one decode and one
re-encode per sentence, on hardware that is often a Raspberry Pi. Naming the Pi is what makes
the cost land, because per-sentence transcoding on a laptop is invisible.

## Theme 8 is where the numbers need the most care

`F8.1` is 858 and it is counted. HANDOFF says "roughly 850" and the audit says "roughly 850".
Quote 858 and cite the `wc -l`. `F8.2` is 206 and it is counted.

`F8.3` is the trap. "About 180 lines survive" is an estimate that came out of a repair plan,
and in a blog post it will read as a diffstat. Any sentence using it has to say it is an
estimate, or the sentence has to use `F8.1` and `F8.2` instead. This is the number most likely
to get quoted back with a "where did that come from".

## Theme 9 exists so no draft can imply this project works

`F9.4` is the fact that governs the tone of every deliverable. The TTS entity raises
`DeepgramRequestError` telling you chapter 5 will implement it. There is no synthesis in this
repo. Three commits (`F9.1`), 314 lines (`F9.2`), six passing tests (`F9.3`), and a config
entry that loads. That is the whole result available to write about.

Which means the honest frame today is the audit plus the design, and the honest ending is what
happens next. Not a launch, not a demo, and not a conclusion. Any draft with a "here is the
finished integration" shape is wrong on the facts, not just overclaiming.

## Theme 10 is a category, not a list

`F10.1` reads as a pile of findings and should not be written that way. Dead code, a function
defined twice, scaffolding from a template generator: the interesting observation is that all
of it came from starting from `ludeeus/integration_blueprint` and never going back to delete
what was not used. That is a category with one cause and one lesson, and it applies to anyone
who has ever started from a template. Itemizing four instances of it at a volunteer's expense
buys nothing.

`F10.2` is the one in that theme with real teeth: a broad `except Exception` two lines
downstream of the code that raises a typed auth error means an expired API key and a dead
network are the same error to a caller. That is worth its own paragraph in a technical piece,
because it is a mistake a competent developer makes while being careful.

## The prior-art tone, stated once so every draft inherits it

Everything in Themes 1, 2, 3, 4, 7, 9, and 10 that is about `alceasan/ha-deepgram-tts` is
about a volunteer's open source integration that people installed and used. It shipped a
working one-shot path against a real API before Flux existed, and it is the reason this project
knows what the shape of the problem is.

The test for every sentence: does a reader learn something they can apply to their own code?
`F2.1` passes, because the streaming opt-in trap catches anyone. `F4.5` passes, because
discovery against the wrong API version is a general failure. A list of dead functions fails,
because the reader learns only that somebody left dead functions in a repo.
