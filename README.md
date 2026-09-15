# Deepgram TTS for Home Assistant

A Home Assistant custom integration that makes [Deepgram Flux TTS](https://deepgram.com) the
voice of a Home Assistant voice assistant.

Flux is the primary path and the default voice. Aura-2 is supported as a second family, because
every Flux voice is English and Aura-2 is the only way to serve a non-English Assist pipeline.

Status: under construction. See `docs/` for the build order.

## Install

Not yet released. When it is: add this repository to HACS as a custom repository of type
`integration`, install, restart, then add **Deepgram TTS** from Settings, Devices and services.

## Requires

- Home Assistant 2026.9.0 or newer
- A Deepgram API key from [console.deepgram.com](https://console.deepgram.com)

## Credits

Prior art: [`alceasan/ha-deepgram-tts`](https://github.com/alceasan/ha-deepgram-tts). This is a
fresh build rather than a fork, but that integration is what proved a Deepgram TTS entity was
worth having and its config flow shape informed this one.

## License

MIT.
