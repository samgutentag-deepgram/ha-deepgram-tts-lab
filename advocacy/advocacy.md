# ha-deepgram-tts-lab advocacy

**Publish or remove this directory before this repo goes public.** It holds
unpublished drafts, and it is one directory so that removing it is one command.

## The claim

In Home Assistant, defining async_stream_tts_audio is itself the streaming opt-in. There is no flag. So a TTS integration that implements streaming before it has measured a first-frame number on real hardware ships a voice assistant that fails inside an Assist pipeline while direct tts.speak calls keep working and hide the breakage.

## The reader

Home Assistant integration developers, and anyone wiring a streaming TTS API into a voice assistant

## Surfaces

- `personal_blog`
- `corporate_blog`
- `personal_thread`
- `corporate_thread`

## Where the work is tracked

https://app.asana.com/1/411927538413705/project/1218530151668605

Asana holds phase, schedule, progress and every task's brief. This file holds
the claim, and the claim is frozen: it does not change again even if the work
does. If the claim turns out to be wrong, that is a finding worth writing up,
not an edit to make here.
