# Deepgram TTS for Home Assistant

> ## 🚧 Work in progress. Not released, not supported, do not install this yet.
>
> This repository is an active build, not a product. No tag, no GitHub release, not in the
> HACS default store, and no support of any kind. Several things listed below have never been
> run once. Everything here is accurate as of **2026-09-17** and goes stale fast.
>
> Read [Where this actually is](#where-this-actually-is) first. It is the whole reason this
> README is worth reading, and it lists what has never been tried as plainly as what works.

A Home Assistant custom integration that makes [Deepgram Flux TTS](https://developers.deepgram.com)
the voice of a Home Assistant voice assistant. Flux is the primary path and the default voice.
[Aura-2](https://developers.deepgram.com) is supported as a second family, because every Flux
voice is English and Aura-2 is the only way to serve a non-English Assist pipeline.

This picks up the work started in
[`alceasan/ha-deepgram-tts`](https://github.com/alceasan/ha-deepgram-tts), which proved a
Deepgram TTS entity was worth having. It is a rebuild rather than a git fork, so there is no
shared history, but that integration's config flow shape is what this one's is modeled on and
its limits are what most of the new work here is aimed at. See [Credits](#credits).

## What you need

- Home Assistant **2026.9.0** or newer. That floor is in [`hacs.json`](hacs.json) and HACS
  enforces it.
- A Deepgram API key from [console.deepgram.com](https://console.deepgram.com).

The key is only used for synthesis. Both voice catalogs, `/v1/models` and `/v2/models`, are
public and take no auth at all, which is why the voice picker can show you all 138 voices in the
step right after the key step and why a bad key fails at the key step rather than at the picker.

## Install

Not yet, really. This repository is private and there is no release, so these steps are here to
show the shape of the install rather than to be followed. HACS can add a private repository as a
custom repository only if you have given it a GitHub token with access.

1. In HACS, open the three-dot menu, choose **Custom repositories**, paste this repository's URL,
   and pick **Integration** as the category.
2. Download **Deepgram TTS**, then restart Home Assistant. A custom integration's Python is
   imported once per process, so the restart is not optional here (see
   [When it goes wrong](#when-it-goes-wrong)).
3. Go to **Settings**, **Devices and services**, **Add integration**, and pick **Deepgram TTS**.
4. On **Connect to Deepgram**, paste the API key. The flow synthesizes one throwaway word with it
   before an entry exists, so a typo comes back as "Deepgram rejected that API key" instead of
   becoming a config entry that fails later.
5. On **Pick a voice**, choose a voice. All 138 are in one dropdown, Flux first, with
   `flux-haley-en` preselected. Each option reads like
   `Haley (Flux, American) [flux-haley-en]`, and the model id is in the label on purpose (see
   below).

The entry titles itself after the voice, so you get `Deepgram Flux (Haley)` rather than a second
row called "Deepgram TTS" that you cannot tell from the first one.

If you are iterating on the code rather than installing it,
[`docs/deploying.html`](docs/deploying.html) ranks every way of getting files onto a running
instance by how fast the edit-to-audible-speech loop is, and recommends rsync over ssh for
everything except proving the HACS path itself.

## The voices, honestly

138 voices, merged from Deepgram's two model endpoints at every setup:

| Family | Entries | Languages |
| --- | --- | --- |
| Flux | 36 | English only |
| Aura | 102 (90 `aura-2`, 12 legacy `aura`) | de, en, es, fr, it, ja, nl |

The default is `flux-haley-en`. American, adult, professional and empathetic per its own catalog
metadata, and the voice Deepgram's quickstart uses, so it is the most recognizable default to
land on.

**A non-English Assist pipeline resolves to an Aura voice and never to Flux.** Every Flux voice
in the catalog is English, so there is no Flux voice for a Spanish pipeline to resolve to. That
is the design, not a gap waiting to be filled: a Spanish sentence read in an American English
voice sounds wrong in a way that is easy to talk yourself out of hearing, so the resolver refuses
to do it. `es` gets `aura-2-agustina-es`, `de` gets `aura-2-aurelia-de`, and so on down the seven
languages. Pick a Flux voice for an English pipeline and Home Assistant still gets an Aura voice
when it asks in Spanish.

The configured voice is a preference, not a constraint. There is no language step in the config
flow because the entity resolves a voice per request anyway, and filtering the picker by language
would be filtering on something the entity does not treat as binding. Home Assistant renders that
dropdown as a type-to-filter combo box, so "haley" or "-es" narrows 138 options without an extra
click.

One thing worth knowing about the labels: 61 of the 102 Aura entries report `display_name` as
`null`, so most Aura labels fall back to a title-cased bare name, and that fallback is not
unique. Legacy `aura-asteria-en` and current `aura-2-asteria-en` both come out as "Asteria" with
the same family and the same accent. That is why every label ends in the voice id. It is also the
exact model string the integration sends, which is the thing you want in front of you when you
are comparing this against Deepgram's docs.

## Options

Two options, on the entry's **Configure** screen:

- **Voice.** The same 138-option dropdown as the setup step.
- **Speaking rate.** 0.5 to 1.5 in 0.05 steps. **Flux only**, because `/v1/speak` has no speed
  parameter at all, so an Aura entry gets no slider and a stored speed is dropped rather than
  carried across the switch.

The slider appears based on the voice currently stored in the entry, not the one you are picking
in the same form, because a form's schema is fixed before you touch it. So switching an entry
from Aura to Flux saves, reloads, and shows the slider the next time you open Configure.

## Two voices at once

Add the integration twice. The entry's unique id is the voice id, so a second entry with a
different voice is allowed and a second entry with the same voice aborts as already configured.
`single_config_entry` is deliberately absent from the manifest.

The pairing this is built for:

| Entry | Voice | Serves |
| --- | --- | --- |
| `Deepgram Flux (Haley)` | `flux-haley-en` | the English pipeline, on the primary path |
| `Deepgram Aura (Celeste)` | `aura-2-celeste-es` | a Spanish pipeline, which Flux cannot serve |

Both entries share nothing but the API key, and each is a separate `tts.` entity you can point a
separate Assist pipeline at. That pairing is the reason both families are in here rather than only
the primary one. Flux being English-only is a hard limit, and a second entry is how you get around
it without a second integration.

## Where this actually is

No release, no tag, not in the HACS default store. Verified 2026-09-17.

### What works

- **It speaks.** A real Home Assistant 2026.9.2 ran with the integration installed, the real
  config flow created a real entry against a real API key, and it spoke in all seven supported
  languages with the correct voice family each time. Then it played through a Sonos Beam in a
  living room. That is a speaker in a house making a sound, not a passing test.
- **122 tests pass on `main`**, 0 failures, ruff clean. The suite runs against real Home
  Assistant 2026.9.2 with `pytest-homeassistant-custom-component`, not against a mock of Home
  Assistant.
- **Batch synthesis is the path `main` uses.** One `async_synthesize` method routes on the model
  prefix: `flux-*` to `POST /v2/speak`, everything else to `POST /v1/speak`. Posting an Aura
  model to `/v2/speak` is rejected by the API, so the prefix is the only routing signal there is.
- **Streaming is written, measured, and deliberately not merged.** It lives on
  `chapter-6-streaming`, five commits ahead, 132 tests passing. In Home Assistant, overriding
  `async_stream_tts_audio` **is** the opt-in for streaming, there is no flag, and the moment the
  method exists every Assist pipeline response routes down it while direct `tts.speak` calls
  keep working. It stays on the branch until the first two items below have been tried. That is
  exactly how the integration this one picks up from shipped broken.

### What has never been tried

The honest half, in priority order:

1. **A real Assist pipeline, end to end.** Only `tts.speak` and `tts_get_url` have been
   exercised. Assist uses the streaming path, which is the one with the trap, and it is what
   every real user hits first.
2. **Streaming through the Sonos audio clip path.** Sonos is handed a `streamUrl` and fetches it
   itself. If it buffers the whole clip before playing, streaming is inaudible through a Sonos
   and the entire chapter-6 branch buys nothing on that speaker.
3. **The options flow, live.** Change voice, change speed, confirm the entry reloads. Unit
   tested only.
4. **Two entries side by side**, one Flux and one Aura. Unit tested only.
5. **Anything at all on a Raspberry Pi.** Every number in this README is from a MacBook.

## Latency, measured

Measured on a MacBook, arm64, over wifi, twice with two independent harnesses that agree.
**None of this is a Raspberry Pi** and none of it goes through Home Assistant, so the ffmpeg
conversion Home Assistant needs is not included.

| | median |
| --- | --- |
| socket connect to `Connected` | 96 ms |
| first `Speak` to first audio frame | 314 ms |
| batch, whole clip returned | 3394 ms |

Two numbers worth taking from that, and one worth ignoring:

- **Streaming reaches first sound 10.8x faster than batch**, same machine, same network, same
  text, same voice. The comparison is the defensible claim, not the absolute.
- **Realtime factor is 1.56x.** Audio arrives 1.56 times faster than it plays, so a player that
  starts on the first frame never starves. Below 1.0 the streaming design would be pointless.
  This is the number that decides whether streaming is worth building at all.
- **Ignore "as low as 80 ms".** A ping to `api.deepgram.com` from here is 72 ms, so 73 ms of the
  314 ms is one round trip that no implementation can avoid. An 80 ms time-to-first-audio is
  barely above that floor, which means it has to be measured from inside Deepgram's network. It
  is not reachable from a house on this coast and should not be repeated as though it were.

## What it costs

Flux TTS is **$0.045 per 1,000 characters** as of 2026-09-15. Home Assistant caches TTS output by
default, so repeated phrases like a morning briefing are billed once rather than once per play.
Check [Deepgram's pricing page](https://deepgram.com/pricing) before you plan around that number.

## When it goes wrong

**You edited a `.py` file and nothing changed.** Restart Home Assistant. Python caches imported
modules in `sys.modules`, so once `custom_components.deepgram_tts.tts` is imported, that object is
what the process has, and rewriting the file changes nothing about the running interpreter.
`homeassistant.reload_config_entry` re-runs setup against the module already loaded, which is
genuinely useful for a changed option, a retried catalog fetch, or a replaced API key, and does
nothing at all for a code edit, a new module, `manifest.json`, or `strings.json`. Same for HACS:
downloading an update writes files and does not reload code.

**The entry sits in a retry loop instead of failing.** That is on purpose. A failed catalog fetch
raises `ConfigEntryNotReady`, so Home Assistant retries with backoff rather than marking the entry
permanently failed, which is what happens when a raw aiohttp error escapes setup. The log line
names both catalog URLs and the underlying error. Worth knowing before you go looking for a bug:
the two catalogs are 205 KB of JSON across two requests at **every** entry setup, 183 KB of which
is `/v1/models`, and the 15 second timeout has never been tested against a Raspberry Pi on wifi.

**You cannot tell whether the key is wrong or the network is down.** You can, and that is
deliberate. An expired or rejected key raises `DeepgramAuthError` and the config flow says
"Deepgram rejected that API key". DNS, TCP, TLS, and timeout failures raise
`DeepgramConnectionError` and the flow says "Could not reach api.deepgram.com". They are separate
typed errors, reraised before any broad handler, and the log says which one happened. The
integration this replaces wrapped the whole synthesis call in a bare `except Exception` that
rewrapped its own auth error, so a caller could not tell the two apart at all.

**A Spanish request came out in an English voice.** Turn on debug logging and read the resolved
model id rather than judging by ear, because this failure does not raise:

```yaml
logger:
  default: warning
  logs:
    custom_components.deepgram_tts: debug
```

Any resolved model starting with `flux-` on a non-English request is a bug worth an issue. An
`aura-` or `aura-2-` model is correct.

## Credits

[`alceasan/ha-deepgram-tts`](https://github.com/alceasan/ha-deepgram-tts) is the prior art this
work picks up from. It is a rebuild rather than a git fork, so the two share no commits, but that
integration is what proved a Deepgram TTS entity was worth having and its config flow shape is
what this one's is modeled on. The new work here is Flux as the primary path, a merged 138-voice
catalog, per-request language resolution across two model families, typed auth and connection
errors that a caller can actually tell apart, and a streaming client held back until it is
measured. Thanks for doing it first.

Deepgram's [Flux TTS](https://developers.deepgram.com) and
[Aura-2](https://developers.deepgram.com) do the actual speaking.

## License

MIT. See [`LICENSE`](LICENSE).
