# Starter prompts

Paste one of these into a fresh Claude Code session with this repo as the working directory.

---

## First session: chapter 1

```
Read HANDOFF.md end to end before doing anything. It is self-contained and every fact in
sections 3 and 4 was verified live on 2026-09-15, so do not re-derive them from the public
docs and do not fetch anything to double-check them. Section 5 is settled; do not reopen it.

We are building a Home Assistant custom integration that makes Deepgram Flux TTS the voice of
a Home Assistant voice assistant. Flux is the primary path and the default voice. Aura-2 stays
supported because every Flux voice is English.

This is a fresh build, not a fork. Nothing is copied from the community integration at
~/Developer/ha-deepgram-tts. Section 2.2 of the handoff lists that codebase's defects; treat
that table as a checklist of things not to do.

Build chapter 1 from the build order in section 6: the scaffold.

  custom_components/deepgram_tts/
    __init__.py        config entry setup and unload, ConfigEntryNotReady on a failed catalog fetch
    const.py           DOMAIN, DEFAULT_VOICE, the two base URLs, the two catalog URLs
    manifest.json      domain, name, my codeowner, config_flow true, integration_type service,
                       iot_class cloud_polling, requirements listing every third-party import
    strings.json
    translations/en.json
  hacs.json            homeassistant floor 2026.9.0
  .github/workflows/   hassfest and HACS validation
  pyproject.toml        ruff config
  tests/               skeleton with current pytest-homeassistant-custom-component
  README.md            stub, credits alceasan/ha-deepgram-tts as prior art

Constraints for every chapter:
- Python 3.14, asyncio.timeout, never async_timeout. No pydub, ever.
- Split language codes on hyphen, never underscore.
- Declare every third-party import in manifest requirements, or use none.
- Do not set single_config_entry and do not fake it with a constant unique_id. Two entries,
  one Flux and one Aura, must be possible.
- No OptionsFlow __init__ that takes or assigns config_entry.
- 2-space indent in JS/TS if any appears; single quotes; no semicolons unless required.
- Comments only where the why is not obvious.

Stop when hassfest and HACS validation pass locally and the entry loads with a placeholder
entity. Do not start chapter 2. Report what you built and what the next chapter needs from me,
specifically whether you need a Deepgram API key in the environment.

One commit for the chapter, conventional commit message.
```

---

## Later sessions: any chapter

```
Read HANDOFF.md, then `git log --oneline` to see which chapters have landed.

Build chapter N from section 6. Same constraints as always: asyncio.timeout not async_timeout,
no pydub, hyphen not underscore for language codes, every third-party import declared, section 5
is settled and not up for discussion.

Before you start, tell me your plan for the chapter in five lines or fewer and wait for a yes.

When the chapter is done, append to .hub/ledger.md: what you chose, what it cost, and anything
that surprised you. Only what a repo scan cannot recover. Then one commit.
```

---

## Chapter 6, the one with real risk

Use this instead of the generic prompt when you get there.

```
Read HANDOFF.md, sections 3.5 and 4.2 especially.

Build chapter 6: streaming over the Flux TTS websocket.

The shape: open wss://api.deepgram.com/v2/speak?model=<flux voice>, send one Speak per chunk of
request.message_gen as it arrives, send Flush when the generator is exhausted, and yield binary
frames until SpeechMetadata. The server places flush boundaries internally, so do not split
sentences, do not buffer the message, and do not stitch fragments. If you find yourself writing
a regex over the text, stop and re-read section 3.5.

Then: prepend a WAV header and report extension="wav", advertise preferred_format in
supported_options, and fall back to the /v2/speak batch endpoint when the socket fails or when
the selected voice is Aura.

Two things I want measured, not assumed:
1. Time from the first Speak to the first audio frame, on the real hardware.
2. What happens when the socket drops mid-turn. It must degrade to batch, not raise.

Chapter 5 must already be running on my real Home Assistant instance before you start. Confirm
that with me first.
```

---

## Notes on using these

- Chapter 5 goes on the real Home Assistant instance before chapter 6 starts. That is the gate
  that turns the streaming work from theoretical into verifiable.
- `/project-hub init` needs a go-ahead before it runs, because it writes to Asana.
- `/advocacy-intake` waits until chapter 5 is on real hardware. There is nothing honest to claim
  before that, and `advocacy-cycle` will not run without a frozen claim anyway.
- If a session ends mid-chapter, `/handoff` snapshots it. This file and `HANDOFF.md` stay the
  durable record; a `/handoff` snapshot is the transient one.
