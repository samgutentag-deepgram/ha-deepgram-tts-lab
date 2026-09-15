# Hardware notes: raw facts and citations

Companion to `docs/hardware-bom.html`. This file is the machine-readable half: every fact that
document rests on, with its source, the date it was checked, and how much weight it carries.
Written 2026-09-15. Nothing here was recalled from memory; everything was fetched.

Weight labels used below:

- **source** means read directly from code, a vendor's own product page, or official docs.
- **weak** means a search snippet, a forum post, a review, or a page that would not load.
- **inferred** means I derived it and did not measure it.

---

## 1. Home Assistant internals (read from source 2026-09-15)

All from `home-assistant/core` @ `dev`.

### homeassistant/components/tts/__init__.py

| Fact | Detail | Weight |
| --- | --- | --- |
| `_DEFAULT_FORMAT` | `"mp3"` (line 107) | source |
| `ResultStream.url` | `f"/api/tts_proxy/{self.token}"` (line 518) | source |
| `ResultStream.media_source_id` | media source id under `MEDIA_SOURCE_STREAM_PATH/{token}` | source |
| `async_set_message` | docstring: "This method will leverage a disk cache to speed up generation." | source |
| `async_set_message_stream` | docstring: "This method can result in faster first byte when generating long responses." | source |
| `TextToSpeechView` | `url = "/api/tts_proxy/{token}"`, `requires_auth = False` | source |
| Proxy response shape | `web.StreamResponse()`, `prepare()` on first chunk, `write(data)` per chunk, `write_eof()` at end. No Content-Length, no range support. | source |
| HEAD handler | Exists with comment: "This is sent by some DLNA renderers, like Samsung ones, prior to sending the GET request." | source |
| `_async_convert_audio` | Shells out to ffmpeg. For an async-generator input with `from_extension == "wav"` it adds `-probesize 32` with comment "The container is known, so minimize probing latency for live TTS audio." | source |
| `tts.speak` schema | Requires `media_player_entity_id` and `message`; `cache` optional, `default=DEFAULT_CACHE` (true) | source |

### homeassistant/components/esphome/assist_satellite.py

Two distinct TTS delivery paths, selected by device feature flags:

| Path | Condition | Behavior | Weight |
| --- | --- | --- | --- |
| HA pushes PCM | `VoiceAssistantFeature.SPEAKER` set | `_stream_tts_audio()` streams the `ResultStream` to the device over the ESPHome API or UDP. Hard requirement: `if tts_result.extension != "wav": _LOGGER.error("Only WAV audio can be streamed, got %s", ...)` and return. Defaults 16 kHz, 16-bit, mono, 512 samples per chunk. Paced with comment: "The ring buffer in the remote device is fixed at 512ms. We want to keep it at around 384ms (75% full)". | source |
| Device pulls URL | `SPEAKER` not set, device has a media player | `_update_tts_format()` reads the device's advertised ANNOUNCEMENT format and sets `ATTR_PREFERRED_FORMAT` / `_SAMPLE_RATE` / `_SAMPLE_CHANNELS` / `_SAMPLE_BYTES`. On `VOICE_ASSISTANT_TTS_END` it sends the device `{"url": ...}` from `tts_output["url"]`. | source |

### esphome/home-assistant-voice-pe @ dev, home-assistant-voice.yaml

Lines 1644 to 1662, `media_player: - platform: speaker_source`:

```yaml
    announcement_pipeline:
      format: FLAC     # FLAC is the least processor intensive codec
      num_channels: 1  # Stereo audio is unnecessary for announcements
      sample_rate: 48000
```

So a Voice PE announcement is FLAC, mono, 48 kHz. HA transcodes our WAV to that with ffmpeg.
**source**

### home-assistant/frontend @ dev, src/translations/en.json

`media-browser` block contains `"web-browser": "Web browser"` alongside `"choose_player": "Choose player"`.
This is the zero-dollar playback target in the Media panel. **source**

### home-assistant/addons @ master (pushed 2026-09-15)

Root directories include `vlc`, `assist_microphone`, `openwakeword`, `piper`, `whisper`,
`speech_to_phrase`. **source**

- `vlc/config.yaml`: `version: 1.1.0`, `audio: true`, arch `aarch64` and `amd64`, `ingress: true`,
  discovery `vlc_telnet`. **source**
- `assist_microphone/config.yaml`: `version: 1.3.0`, `audio: true`. **source**
- `home-assistant.io/integrations/vlc_telnet/`: "You can run a VLC Media Player on your Home
  Assistant installation using the official VLC app." **source**

### Claims I could not pin to source

- **HA OS exposes no `media_player` for locally attached audio.** Supported by several community
  threads (Local Speaker as Media Player; WTH is with the SIMPLE local audio playback) and by the
  fact that an official VLC app exists at all. No single authoritative doc says it. **weak**
- **`assist_satellite.announce` vs `tts.speak` on a Voice PE.** The dev.to post
  "No audio from the Home Assistant Nabu puck: use assist_satellite.announce" (dated 2024-06-23)
  describes `tts.speak` at the satellite's media player updating state without producing sound.
  The code path in `assist_satellite.py` is consistent with it. Post itself is **weak**; use the
  code as the real authority.

---

## 2. Protocols and satellite software

| Fact | Value | Source | Weight |
| --- | --- | --- | --- |
| `rhasspy/wyoming-satellite` archived | `"archived": true`, `"pushed_at": "2026-01-24T13:20:36Z"`, 1243 stars, 212 open issues | api.github.com, checked 2026-09-15 | source |
| Archive date | Archived by the owner on 2026-01-27, now read only | search snippet of the repo page | weak |
| Replacement | "replaced by Linux Voice Assistant that uses the ESPHome protocol, which supports the newest features (e.g, media player, stop wake word, start/continue conversation, and timers)" | search snippet quoting the archived repo notice | weak |
| `OHF-Voice/linux-voice-assistant` | `"archived": false`, `"pushed_at": "2026-09-03T19:33:40Z"`, 618 stars, 73 open issues, Apache-2.0, created 2025-08-06 | api.github.com, checked 2026-09-15 | source |
| Repo renamed | `OHF-Voice/hav-sat` returns byte-identical metadata, so it is the same repo behind a rename redirect | api.github.com, checked 2026-09-15 | source |
| LVA requirements | "1Ghz CPU, min. 512MB memory, and around 4GB storage", linux/amd64 or linux/aarch64, 16 kHz mono audio, PulseAudio, "any microphone that works with PipeWire can in theory be used" | README, main branch | source |
| LVA status | "an experimental voice satellite software for Home Assistant remote voice control" | README | source |
| LVA recommended hardware | Pi Zero 2 W + Satellite1 HAT, or Pi 3+ with ReSpeaker Lite | README | source |
| microWakeWord needs ESP32-S3 | "ESP32-S3 is recommended ... the new algorithms will no longer support ESP32 chips"; Atom Echo streams audio and lets HA do wake word instead | HA Voice Chapter 6 blog (2024-02-21) via search snippet | weak |
| `esphome.io/components/micro_wake_word` | Page states no explicit variant requirement; only mentions PSRAM for `task_stack_in_psram` | vendor docs | source |
| Deepgram STT integration | `Automaat/deepgram-stt`: MIT, created 2026-01-31, pushed 2026-09-15, 1 star, 3 open issues, not archived, "Deepgram Speech-to-Text integration for Home Assistant", Nova-3 | api.github.com, checked 2026-09-15 | source |
| Browser-as-satellite | `jxlarrea/voice-satellite-card-integration`, AGPL-3.0, creates both `assist_satellite` and `media_player` entities, needs HA 2025.6.1+, HTTPS, and the screen to stay on | repo page, checked 2026-09-15 | source |
| Android companion TTS | `message: "TTS"` with `tts_text`; "Current support is limited to the current Text To Speech locale set on the device". Uses the phone's own engine, not a HA TTS entity. Android only. | companion.home-assistant.io | source |

---

## 3. Playback paths that break a time-to-first-audio measurement

| Path | Number | Source | Weight |
| --- | --- | --- | --- |
| Snapcast buffer | "The default is 1000 ms and it can be set between 200 and 6000." Chunk size default 26 ms. | music-assistant.io/player-support/snapcast/ | source |
| Snapcast in HA | `snapcast.set_latency` action exists, so latency is a first-class knob | home-assistant.io/actions/snapcast.set_latency/ | source |
| Music Assistant announcements | If a player has no native announce, MA stops music, adjusts volume, plays, restores. Community reports of 10 to 20 second delays (MA support issue 4568, discussion 3770). | music-assistant.io + issue threads | weak |
| Chromecast live streams | pychromecast issue 356: stuck in BUFFERING for about 20 s on a live stream, versus about 1 s for a static MP3 URL | GitHub issue, old | weak |
| DLNA renderers | HA's own TTS proxy carries a HEAD handler specifically for Samsung DLNA renderers, and returns no Content-Length | core source | source |
| HA TTS cache | `tts.speak` defaults `cache: true`, and `async_set_message` uses a disk cache. Repeat the same sentence and you measure the cache. | core source | source |

---

## 4. Prices and availability

Every row checked **2026-09-15**. "Vendor page" means the seller's own product page.

| Item | Price | Stock wording | Where | Weight |
| --- | --- | --- | --- | --- |
| HA Voice Preview Edition | "$69 / 59€" MSRP | none given | home-assistant.io/voice-pe/ (official) | source |
| HA Voice Preview Edition | $58.95 | "In stock" | ameridroid.com (vendor page) | source |
| HA Voice Preview Edition | $58.95 | "239 in stock" | cloudfree.shop (vendor page) | source |
| ESP32-S3-BOX-3 | $49.95 | "Out of stock" | adafruit.com/product/5835 (vendor page) | source |
| ESP32-S3-BOX-3 | not obtained | "43 units in stock" at Mouser, "ships today" at DigiKey | search snippets only; Mouser timed out twice, DigiKey returned 403, Octopart 403, Amazon body not parseable | weak |
| M5Stack ATOM Echo | "Regular price $13.50 USD" | "10+ In Stock" | shop.m5stack.com (vendor page). Mic SPM1423 PDM, speaker 0.8 W via NS4168 | source |
| M5Stack Atom EchoS3R | "Regular price $14.50 USD" | "10+ In Stock" | shop.m5stack.com (vendor page). ESP32-S3-PICO-1-N8R8, ES8311 codec, NS4150B + 8Ω 1 W speaker | source |
| ReSpeaker Lite Voice Assistant Kit, full kit | $26.99 | not stated | seeedstudio.com (vendor page). XIAO ESP32S3 pre-soldered, 2-mic array, XMOS XU316, 4R 5W enclosed speaker, acrylic case | source |
| ReSpeaker 2-Mics Pi HAT V2.0 | $13.99 (10+ $11.99) | "In stock" | seeedstudio.com (vendor page) | source |
| ReSpeaker XVF3800 USB 4-Mic Array with case | $59.90 (10+ $54.90) | "In stock" | seeedstudio.com (vendor page). XMOS XVF3800, AEC/AGC/DoA/VAD/beamforming, 360 degree pickup to 5 m, USB or I2S | source |
| ReSpeaker XVF3800 bare board | about $49.99 | unknown | search snippet | weak |
| Satellite1.1 HAT Board | "$54.99 USD" | "Available on backorder — Restock Jul 15, 2026" | futureproofhomes.net (vendor page). Restock date is in the past as of today, so real availability is unknown. 4 mics, XMOS XU316, 25 W mono amp via TAS2780, headphone jack | source |
| Raspberry Pi Zero 2 W | $17.25 | no stock wording, "Maximum Purchase: 1 unit" | pishop.us (vendor page) | source |
| Raspberry Pi Zero 2 W with headers | $20.75 | no stock wording | pishop.us (vendor page) | source |
| Adafruit Mini External USB Stereo Speaker (3369) | $12.50 | "In stock" | adafruit.com (vendor page). USB powered and USB audio, 2 x 2 W, no 3.5 mm jack | source |
| Adafruit USB Audio Adapter (1475) | $4.95 | "In stock" | adafruit.com (vendor page). Output plus line-level input | source |
| Adafruit Mini USB Microphone (3367) | $5.95 | "In stock" | adafruit.com (vendor page). "needs no driver" | source |
| Adafruit 3.5mm Male/Male Stereo Cable (2698) | $2.50 | "3 in stock" | adafruit.com (vendor page). 1 m | source |
| Creative Pebble V3 | $42.74 | Buy button present, no count | us.creative.com (vendor page). USB-C audio, Bluetooth 5.0, 3.5 mm aux in, 8 W RMS | source |
| Seeed Mono Enclosed Speaker 4R 5W | about $2 | unknown | appeared in an "Also Add" module on a Seeed page, not its own product page | weak |

### Deepgram pricing, checked 2026-09-15 on deepgram.com/pricing (vendor page, source)

| Model | Pay as you go | Growth |
| --- | --- | --- |
| Flux TTS | $0.0450 / 1k characters | $0.0405 / 1k characters |
| Aura-2 | $0.030 / 1k characters | $0.027 / 1k characters |
| Aura-1 | $0.0150 / 1k characters | $0.0135 / 1k characters |
| Nova-3 monolingual STT | "Current price $0.0048/min Regular price $0.0077/min" | $0.0042/min current |
| Nova-3 multilingual STT | $0.0058/min current | $0.0050/min current |

Flux TTS matches HANDOFF section 3.5.

---

## 5. Reviews and subjective quality (all weak by nature)

From a search over Voice PE reviews (Smart Home Solver, Matter Alpha, Botmonster, michaelsleen.com),
checked 2026-09-15:

- Speaker "is not good for streaming music, but it's fine for audio responses", "too quiet for a
  kitchen", "the included DAC is capable of playing lossless audio on a suitable external speaker".
- Mics: one reviewer "pleasantly surprised" at normal speaking volume in a small room, another had
  to "get quite close to the device before the wake word was recognized". Far-field "holds up at
  four meters" but "wake word accuracy drops in noisy rooms".

Treat all of it as directional. The only figure worth repeating is that the 3.5 mm jack has its own
DAC, which is in the official spec sheet too.

---

## 6. Inferred, not measured

Label these as inferred anywhere they appear.

1. **Device-side latency on the HA-pushes-PCM path is roughly 0.3 to 0.5 s.** Derived from the
   pacing code's own comments: a 512 ms ring buffer held at about 384 ms. Not measured.
2. **The FLAC transcode hop costs tens of milliseconds, not hundreds.** Derived from it being one
   ffmpeg spawn with `-probesize 32` and a streaming codec. Not measured.
3. **A browser tab is the loosest measurement target of all**, because its media element buffering
   is not under HA's control and varies by browser. Not measured.
4. **Two Voice PE units on the same 2.4 GHz network will not contend meaningfully** at these bit
   rates. Reasoned, not tested.

---

## 7. Open questions for whoever picks this up

1. What sample rate does the Flux websocket emit `linear16` at? HANDOFF 3.4 says `sample_rate` is
   rejected for mp3 and the socket emits raw linear16, but the rate itself is not recorded. It
   matters, because the ESPHome PCM path wants 16 kHz mono and the Voice PE wants 48 kHz, and HA
   will resample either way. Find it in chapter 2.
2. Does `assist_satellite.announce` reach our TTS entity with a streamed message or a single
   string? Chapter 6 verification depends on which.
3. Is the ESP32-S3-BOX-3 genuinely stocked at Mouser and DigiKey? Neither page would load.
4. Does the Atom EchoS3R have a supported ESPHome voice assistant config? M5Stack's docs imply
   Home Assistant use and a customer review mentions it, but there is no HA or ESPHome page for
   that specific board.
5. Real stock status of the Satellite1.1 HAT, whose own page shows a restock date two months in
   the past.
