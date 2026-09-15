# Chapter 2 notes: the API client

Written while building `api.py`. Notes an agent reads, so this stays markdown.

## What I chose

- **`_build_params` is a module-level function, not a method.** It takes no client state, so
  keeping it out of the class makes the routing decision and the parameter decisions separately
  testable and separately readable. Same for `_extension_for` and `_error_for`.
- **The error body is read once as bytes and parsed with `json.loads`, not `response.json()`.**
  `response.json()` raises `ContentTypeError` when the header is not JSON, which would mean the
  error handler has its own failure mode. Reading bytes and trying to parse them means a proxy's
  HTML 502 page can only ever produce a `DeepgramRequestError`.
- **`async_verify_key` catches `DeepgramError`, not each subclass.** One handler above the broad
  one covers all four typed errors, and it cannot drift when a fifth is added.
- **`SynthesisResult.content_type` is the header verbatim**, including an empty string when the
  API sends none. Callers get the extension already derived, but nothing is hidden from them.
- **`container=none` is excluded from the extension fallback chain.** It means raw frames with no
  wrapper, so using it as a file extension would produce `speech.none`. Unmapped content type plus
  `container=none` falls through to `encoding`.
- **The content-type map is short on purpose.** Only the eight the contract names. The fallback
  chain, requested container then requested encoding then mp3, is always available, so a guess
  never buys anything.
- **`live_check.py` runs the catalog half before it checks for a key.** Exiting 2 first would mean
  the only part verifiable without a key never runs. It still exits 2 and says why.
- **`live_check.py` writes `.bin`, not `.mp3`.** The script's job is to let a human judge the
  container from the header and the first four bytes. Naming the file `.mp3` would presume the
  answer.

## What surprised me

- **`pytest-homeassistant-custom-component`'s `aioclient_mock` records `mock_calls` as
  `(method, url, data, headers)` with `method` upper-cased**, so an assertion against `"post"`
  fails. The URL is a `yarl.URL` with the query attached, which is what makes "assert on the URL
  actually called" cheap: `url.path` and `url.query` are both there.
- **The `client` fixture has to depend on `aioclient_mock` and be `async`.** `aioclient_mock`
  patches `_async_create_clientsession`, and `hass` caches the session on first use, so a sync
  fixture that resolves before the mock gets a real session and tries to hit the network. That
  failure reads as `'NoneType' object has no attribute 'getaddrinfo'`, which names nothing useful.
- **`asyncio.timeout` plus the request context manager fit in one parenthesized `async with`**, so
  there is no nesting and no separate `try` for the body read.
- **Both live catalog counts still match HANDOFF section 3.3 exactly** (36 `flux-tts` from
  `/v2/models`; 102 from `/v1/models`, which breaks down as 90 `aura-2` plus 12 `aura`). Nothing
  drifted in the 14 hours between the audit and this chapter, which is the expected answer but
  worth having on record as a measurement rather than an assumption.

## Still unverified

1. **Nothing authenticated has run.** There is no Deepgram API key on this machine, so
   `async_verify_key` and both `/speak` round trips are exercised only against mocks.
   `scripts/live_check.py` closes that gap in one command as soon as a key exists. Everything in
   HANDOFF section 7 item 1 is still open.
2. **`sample_rate` with `encoding` unset.** The contract says to drop `sample_rate` when `encoding`
   is `"mp3"`, and that is what the code does. But mp3 is also the default encoding when none is
   requested, so `sample_rate=24000` with no `encoding` may hit the same "not applicable"
   rejection. HANDOFF section 3.4 records `/v1/speak` documented defaults as mp3 *and*
   `sample_rate=24000` together, which suggests v1 tolerates it and says nothing about v2. This is
   an underspecified corner of the contract, not a defect in it. A live check can settle it.
3. **The extensions for `audio/basic` and `audio/l16`.** `mulaw` and `pcm` are the right names for
   those encodings, but neither is a container, and whether HA's `_async_convert_audio` accepts
   them as an ffmpeg format hint is untested. Chapter 5 will find out, and the batch path only
   reaches them if something asks for `encoding=mulaw` or `linear16` with `container=none`.
4. **Whether a real 401 body is JSON.** The 403 and non-JSON test cases cover both shapes, so the
   client does not care, but the message a user sees in the config flow depends on it.
