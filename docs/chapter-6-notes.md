# Chapter 6 notes: streaming

**This chapter is on the `chapter-6-streaming` branch and is not merged.** Read
`docs/superpowers/build-plan.md` section 3 for why, but the short version is that defining
`async_stream_tts_audio` is itself the opt-in, so merging it turns streaming on for every
Assist response in the house at the moment of the merge. The gate is a measured first-frame
latency on the real instance, produced by `scripts/measure_first_frame.py`.

## What it does

`tts.py` gains `async_stream_tts_audio`. `api.py` gains `DeepgramClient.stream()`, which hands
back a `FluxSocket` so the API key stays in the object that owns it and the entity never holds a
copy. `stream.py` was already on main and unchanged by this chapter.

Both the socket and the batch fallback produce WAV, and the extension is declared as `wav`
before a single byte is fetched. That is forced: `TTSAudioResponse` wants the extension up
front, and the socket can fail at any point, so if the two paths produced different containers
there would be nothing to reconcile them with.

It also happens to be the right format. An ESPHome voice satellite advertising the speaker flag
hard-refuses anything else with "Only WAV audio can be streamed", per the hardware research in
`docs/hardware-notes.md`. Returning mp3 would have put us on the slow branch for nothing.

## The two failure windows, which need different answers

This is the design decision in the chapter.

**Before any audio has reached the caller**, the whole turn can still be served from
`/v2/speak` and a listener hears no difference. That is the clean fallback and it is what
settled decision 5 asks for.

**Once audio has gone out**, a batch clip cannot be appended. It arrives with its own 44 byte
RIFF header, which would land in the middle of the stream, and the result is a file that decodes
to the first half followed by garbage. So the turn ends where it ends and the log says why.
Truncated speech is bad. A second WAV header mid-stream is worse, because it fails in a way
nobody can diagnose from listening.

To keep the first window as wide as possible, the entity **holds the socket's WAV header** until
the first real audio frame arrives. A header already sent is what makes a clean fallback
impossible, so it costs 44 bytes of delay and buys the entire fallback window.

## The text copy, which is not the buffering the handoff warns about

`message_gen` is single use. A fallback that has to re-synthesize the turn has no other way to
know what the text was, so `_tee` keeps a copy of each chunk while forwarding it.

HANDOFF section 2.2 says not to buffer `request.message_gen` into one string before the first
synthesis call. That is a different thing: nothing here waits. Each chunk is yielded the instant
it arrives and the copy is a side effect.

Draining the rest of a generator whose consumer was cancelled mid-iteration can leave it in a
state that raises, so that drain is guarded. A failure to drain costs the tail of the sentence
rather than the whole turn.

## What landed as verification, and one thing it settled

`tests/test_tts_streaming.py`, 10 tests, driving the real tts manager with `ws_connect` faked at
the session. The real `FluxSocket` and the real entity run; only the network is replaced.

**`test_the_streaming_wav_survives_home_assistants_own_ffmpeg_pass` settled an open question.**
`stream.py` writes `0xFFFFFFFF` into both RIFF size fields, because a stream cannot know its own
length and inventing one would mean buffering the clip. Nothing had confirmed anything
downstream accepts that. Asking the manager for mp3 while the entity produces wav forces
`_async_convert_audio`, which shells out to real ffmpeg on this machine, and it converts
cleanly. So the sentinel header is readable by the converter every Home Assistant install has.

Still unverified: whether a **playback device** is as tolerant as ffmpeg. The hardware research
found a HEAD handler in core whose comment says it exists for Samsung DLNA renderers, which is a
map of which devices break on a stream with no Content-Length.

## The trap, reproduced in our own test suite

Worth recording because it happened here rather than in the codebase being replaced.

Adding `async_stream_tts_audio` broke 15 tests that had nothing to do with streaming. Thirteen
of them drove `async_get_media_source_audio`, which is how Home Assistant itself synthesizes, so
the moment the method existed the manager routed all of them down the websocket. They were
written as batch tests and had silently become fallback tests.

That is HANDOFF section 2.1 exactly: one method coming into existence changes how everything is
served, and nothing announces it. In the test suite it showed up as 15 red tests. In production
it shows up as a voice assistant that stops working while `tts.speak` keeps passing.

The batch tests now call `async_get_tts_audio` by name. Chapter 5's guard assertion was inverted
rather than deleted: it now asserts streaming **is** supported and the method **is** in the
class dict, because the fact it pins has not changed. If the method is ever removed or renamed,
streaming turns off silently and every pipeline reverts to batch with nothing failing.

## Open, and needs the real instance

1. **First-frame latency.** Unmeasured. `scripts/measure_first_frame.py --runs 20` on the Pi.
   Report median and p95, never a single sample, and never without the hardware named.
2. **The sample rate.** `WS_SAMPLE_RATE` is 24000 and the socket is asked for it explicitly, but
   nobody has confirmed what Flux actually emits, and the two playback paths want 16 kHz
   (ESPHome speaker flag) and 48 kHz (Voice PE fetching FLAC). `stream.py` checks its own math
   against `audio_duration_ms` and warns on a mismatch; the first live turn is what reads that
   warning.
3. **`tts.speak` defaults to `cache: true`**, which is the single biggest threat to the latency
   measurement. A cached second call measures the cache. Every measurement must pass
   `cache: false`.
4. **Whether a real playback device tolerates the unknown-length header.** ffmpeg does. Nothing
   else has been asked.
5. **Barge-in stays out of scope.** `SpeechInterrupted.text_spoken` is the right primitive and
   Home Assistant's TTS entity API has no hook for it. Settled decision 8.
