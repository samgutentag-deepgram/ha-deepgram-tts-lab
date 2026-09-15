# Changelog

All notable changes to this integration are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing has been released yet, so `[Unreleased]` is the only section here and every line in it is
an addition. There is no `Changed`, `Fixed`, or `Deprecated` section because there is no released
version for anything to have changed from.

Two things are in the tree and deliberately switched off. Streaming over the Flux websocket is
written and not wired into the TTS entity, pending a first-frame measurement on real hardware.
`zip_release` stays `false` in `hacs.json`, so HACS installs from the repository tree and the
release zip is for manual installs only.

### Added

- A Deepgram text-to-speech entity for Home Assistant, set up entirely through the UI. No YAML.
- **Voice catalog merged from both Deepgram endpoints.** 138 voices in one list: 36 Flux voices,
  all English, and 102 Aura voices covering German, English, Spanish, French, Italian, Japanese,
  and Dutch. The list is fetched fresh at every setup, so a voice Deepgram adds shows up without
  an integration update.
- **One voice picker, all 138 voices, Flux first.** Home Assistant renders it as a
  filter-as-you-type dropdown, so typing "haley" or "-es" narrows it. Every option ends in the
  Deepgram model id, because 61 of the Aura voices report no display name and the fallback labels
  collide: two different voices both read as "Asteria" without the id to tell them apart.
- **`flux-haley-en` is the default voice** on a fresh install, preselected in the picker.
- **A non-English pipeline gets an Aura voice, never Flux.** Every Flux voice is English, so a
  Spanish or German request resolves to Aura regardless of which voice the entry is configured
  with. The configured voice is a preference, not a constraint.
- **Speaking rate**, 0.5 to 1.5, on Flux voices only. Deepgram's Aura endpoint has no speed
  parameter, so Aura entries get no slider and a stored rate is dropped rather than silently
  ignored.
- **Multiple entries, one voice each.** Add a Flux voice for English and an Aura voice for another
  language side by side. Each entry titles itself after its voice, for example
  `Deepgram Flux (Haley)`. Adding the same voice twice is refused.
- **The API key is checked before the entry exists.** Setup synthesizes one throwaway word, so a
  bad key is a form error rather than an integration that installs and then fails at the first
  spoken word.
- **A rejected key and an unreachable API are reported as different problems.** "Deepgram
  rejected that API key" and "Could not reach api.deepgram.com" are separate messages, and the
  log says which one happened.
- **A voice catalog that cannot be reached retries** with backoff instead of leaving the entry
  permanently failed. Restoring the network is enough; no restart, no re-add.
- **The language list is base codes only.** `en`, `es`, `de` and so on, never a mix of `en` and
  `en-US` that makes one language look like two in the Assist pipeline picker.
- **Nothing is transcoded locally.** The integration hands Home Assistant whatever audio Deepgram
  returned and lets Home Assistant convert it only when the requested format differs. On a
  Raspberry Pi that is the difference between one conversion and one per sentence.
- **Home Assistant 2026.9.0 is the declared minimum**, enforced by HACS at download time.
- **Every release carries a zip of the integration**, built and attached automatically, for
  manual installs and for anyone not running HACS. The release refuses to build when the version
  in `manifest.json` disagrees with the tag, because HACS reads the version from the manifest and
  a mismatch would report the wrong version forever.
