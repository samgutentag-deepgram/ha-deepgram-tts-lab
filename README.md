# Deepgram TTS for Home Assistant

> ## 🚧 Work in progress. Don't install this.
>
> No release, no tag, not in the HACS default store, no support of any kind. A real Home
> Assistant 2026.9.2 has spoken through a Sonos Beam with this installed, and that is about as
> far as it goes. The Assist pipeline, the options flow, and anything at all on a Raspberry Pi
> have never been run once. Accurate on 2026-09-17 and stale soon after.

Makes [Deepgram Flux TTS](https://developers.deepgram.com) the voice of a Home Assistant voice
assistant. 36 Flux voices, all English, `flux-haley-en` by default.

This picks up the work started in
[`alceasan/ha-deepgram-tts`](https://github.com/alceasan/ha-deepgram-tts). It's a rebuild, not a
git fork, so the two share no commits. See [Credits](#credits).

## What you need

- Home Assistant **2026.9.0** or newer. That floor lives in [`hacs.json`](hacs.json) and HACS
  enforces it.
- A Deepgram API key from [console.deepgram.com](https://console.deepgram.com).

The key only does synthesis. Both voice catalogs are public and take no auth, so the picker
fills itself in the step right after the key step, and a bad key fails at the key step instead of
somewhere confusing later.

## Install

Not yet. The repo is private and there's no release, so these steps are here to show the shape of
the install.

1. In HACS, three-dot menu, **Custom repositories**, paste this repo's URL, category
   **Integration**.
2. Download **Deepgram TTS**, then restart Home Assistant. Python caches imported modules, so a
   full restart is the only thing that picks up new code. HACS downloading an update writes files
   and reloads nothing.
3. **Settings**, **Devices and services**, **Add integration**, **Deepgram TTS**.
4. Paste the API key. The flow synthesizes one throwaway word with it before an entry exists, so a
   typo comes back as "Deepgram rejected that API key" instead of becoming an entry that fails
   later.
5. Pick a voice. Flux sits at the top of the dropdown with `flux-haley-en` preselected.

The entry names itself after the voice, so you get `Deepgram Flux (Haley)` and not a second row
called "Deepgram TTS" that you can't tell from the first one.

## Voices

36 Flux voices, every one of them English. The default is `flux-haley-en`: American, adult,
professional and empathetic per its own catalog metadata, and the voice Deepgram's quickstart
uses.

Options in the picker read like `Haley (Flux, American) [flux-haley-en]`. The model id is in the
label on purpose. It's the exact string the integration sends, which is what you want in front of
you when you're comparing behavior against Deepgram's docs.

### Other languages, through Aura

Every Flux voice is English, so a pipeline in another language has nothing to resolve to. For
that, the picker also carries 102 older [Aura-2](https://developers.deepgram.com) voices covering
de, en, es, fr, it, ja, nl.

The entity picks a voice per request, so a non-English request gets an Aura voice whatever you
chose at setup. `es` gets `aura-2-agustina-es`, `de` gets `aura-2-aurelia-de`, and so on down the
seven languages. A Spanish sentence read in an American English voice sounds wrong in a way
that's easy to talk yourself out of hearing, so the resolver won't do it.

To check what you actually got, turn on debug logging and read the resolved model id:

```yaml
logger:
  default: warning
  logs:
    custom_components.deepgram_tts: debug
```

Anything starting with `flux-` on a non-English request is a bug. `aura-` or `aura-2-` is right.

**Running both at once.** Add the integration twice. An entry's unique id is its voice id, so a
second entry with a different voice is allowed and a duplicate aborts. Point an English Assist
pipeline at `Deepgram Flux (Haley)` and a Spanish one at `Deepgram Aura (Celeste)`. The two share
nothing but the API key.

## Options

On the entry's **Configure** screen:

- **Voice.** The same dropdown as setup.
- **Speaking rate.** 0.5 to 1.5 in 0.05 steps, **Flux only**. The Aura endpoint has no speed
  parameter at all, so an Aura entry gets no slider and a stored speed is dropped on the switch.

The slider keys off the voice currently saved in the entry, not the one you're picking in the same
form, because a form's schema is fixed before you touch it. So switching an entry from Aura to
Flux saves, reloads, and shows the slider the next time you open Configure.

## What it costs

Flux TTS is **$0.045 per 1,000 characters** as of 2026-09-15. Home Assistant caches TTS output by
default, so a morning briefing that says the same thing every day is billed once. Check
[Deepgram's pricing](https://deepgram.com/pricing) before you plan around that number.

## Credits

[`alceasan/ha-deepgram-tts`](https://github.com/alceasan/ha-deepgram-tts) is the prior art this
picks up from. A rebuild and not a git fork, so the two share no commits, but that integration
proved people wanted a Deepgram TTS entity, and its config flow shape is what this one's is
modeled on. New here: Flux as the primary path, per-request language resolution across both model
families, typed auth and connection errors a caller can tell apart, and a streaming client held
back on a branch until it's been measured on real hardware. Thanks for doing it first.

Deepgram's [Flux TTS](https://developers.deepgram.com) and
[Aura-2](https://developers.deepgram.com) do the actual speaking.

## License

MIT. See [`LICENSE`](LICENSE).
