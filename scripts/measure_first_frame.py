#!/usr/bin/env python3
"""Measure time to first audio frame over the Flux TTS websocket, and prove the batch fallback.

HANDOFF section 7 item 2 records that first-frame latency over the socket is unmeasured, and
that Deepgram's marketing claims audio starts in as low as 80 ms. That is a claim to test, not
a fact to repeat, and it has to be measured on the hardware that will run it rather than on a
laptop, because the number a viewer cares about includes the network from their house.

This script exists so that measurement is one command on whatever machine is being tested,
and so the answer lands in a file instead of a memory.

    DEEPGRAM_API_KEY=... python3 scripts/measure_first_frame.py
    DEEPGRAM_API_KEY=... python3 scripts/measure_first_frame.py --runs 20 --voice flux-haley-en

What it reports, per run:
  connect_ms        websocket open to the Connected message
  first_frame_ms    first Speak sent to first binary audio frame. This is the headline number
  metadata_ms       first Speak to SpeechMetadata, meaning all audio for the turn was sent
  audio_ms          audio_duration_ms the server reported
  bytes             total binary bytes received
  realtime_factor   audio_ms / metadata_ms. Above 1.0 means audio arrives faster than it plays,
                    which is the only condition under which streaming playback never starves

Then the distribution across runs, because a single sample of a network measurement is not a
measurement. Median and p95 are reported; the mean is not, because one slow run skews it and
the interesting question is what a listener usually waits.

It also runs a deliberate failure: the socket is closed mid turn and the batch endpoint has to
serve the rest. HANDOFF section 6.1 makes that chapter 6's second verification, and a demo that
survives being broken is the only kind anybody believes.

Stdlib plus aiohttp only, so it runs anywhere this integration runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

try:
    import aiohttp
except ImportError:
    sys.exit("aiohttp is required: pip install aiohttp")

WS_URL = "wss://api.deepgram.com/v2/speak"
BATCH_URL = "https://api.deepgram.com/v2/speak"
DEFAULT_VOICE = "flux-haley-en"
OUT_DIR = Path(__file__).resolve().parent / "out"

# Chunked the way an LLM actually emits tokens, so the measurement reflects the real shape of
# the input. Sending one complete sentence would measure something this integration never does.
TOKEN_CHUNKS = [
    "The back door ",
    "has been unlocked ",
    "since four this afternoon, ",
    "and the garage light ",
    "is still on.",
]


class Timings:
    """One run's numbers."""

    def __init__(self) -> None:
        """Start every field empty so a failed run is distinguishable from a zero."""
        self.connect_ms: float | None = None
        self.first_frame_ms: float | None = None
        self.metadata_ms: float | None = None
        self.audio_ms: float | None = None
        self.total_bytes = 0
        self.speech_started_ms: float | None = None
        self.error: str | None = None

    @property
    def realtime_factor(self) -> float | None:
        """Audio produced per unit of wall time. Above 1.0 means playback cannot starve."""
        if self.audio_ms and self.metadata_ms:
            return self.audio_ms / self.metadata_ms
        return None

    def as_dict(self) -> dict:
        """Flatten to something json.dumps can write."""
        return {
            "connect_ms": _round(self.connect_ms),
            "speech_started_ms": _round(self.speech_started_ms),
            "first_frame_ms": _round(self.first_frame_ms),
            "metadata_ms": _round(self.metadata_ms),
            "audio_ms": _round(self.audio_ms),
            "bytes": self.total_bytes,
            "realtime_factor": _round(self.realtime_factor, 2),
            "error": self.error,
        }


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


async def one_run(session: aiohttp.ClientSession, api_key: str, voice: str) -> Timings:
    """Open a socket, stream the chunks in, and time what comes back."""
    timings = Timings()
    opened = time.perf_counter()

    async with session.ws_connect(
        f"{WS_URL}?model={voice}",
        headers={"Authorization": f"Token {api_key}"},
        heartbeat=None,
    ) as socket:
        # Wait for Connected before the clock that matters starts, so a slow TLS handshake is
        # reported separately instead of hiding inside the first-frame number.
        while timings.connect_ms is None:
            message = await socket.receive()
            if message.type is aiohttp.WSMsgType.TEXT:
                if json.loads(message.data).get("type") == "Connected":
                    timings.connect_ms = (time.perf_counter() - opened) * 1000
            elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                timings.error = f"socket closed before Connected: {message.type}"
                return timings

        first_speak = time.perf_counter()

        async def send_chunks() -> None:
            """Forward each chunk as it arrives, then flush. No sentence splitting.

            The server places flush boundaries internally, which is the whole reason this
            function is five lines and not a two hundred line sentence buffer.
            """
            for chunk in TOKEN_CHUNKS:
                await socket.send_json({"type": "Speak", "text": chunk})
                await asyncio.sleep(0.04)  # roughly an LLM's inter-token gap
            await socket.send_json({"type": "Flush"})

        sender = asyncio.create_task(send_chunks())

        try:
            while True:
                message = await socket.receive()

                if message.type is aiohttp.WSMsgType.BINARY:
                    if timings.first_frame_ms is None:
                        timings.first_frame_ms = (time.perf_counter() - first_speak) * 1000
                    timings.total_bytes += len(message.data)
                    continue

                if message.type is aiohttp.WSMsgType.TEXT:
                    event = json.loads(message.data)
                    kind = event.get("type")
                    if kind == "SpeechStarted" and timings.speech_started_ms is None:
                        timings.speech_started_ms = (time.perf_counter() - first_speak) * 1000
                    elif kind == "SpeechMetadata":
                        timings.metadata_ms = (time.perf_counter() - first_speak) * 1000
                        timings.audio_ms = event.get("audio_duration_ms")
                        break
                    elif kind == "Error":
                        timings.error = f"{event.get('code')}: {event.get('description')}"
                        break
                    continue

                if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    timings.error = f"socket ended early: {message.type}"
                    break
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    return timings


async def batch_fallback(session: aiohttp.ClientSession, api_key: str, voice: str) -> dict:
    """Synthesize the same text over the batch endpoint, for the degradation comparison."""
    started = time.perf_counter()
    async with session.post(
        BATCH_URL,
        params={"model": voice},
        json={"text": "".join(TOKEN_CHUNKS)},
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
    ) as response:
        body = await response.read()
    return {
        "status": response.status,
        "bytes": len(body),
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        "content_type": response.headers.get("Content-Type", ""),
    }


async def drop_mid_turn(session: aiohttp.ClientSession, api_key: str, voice: str) -> dict:
    """Kill the socket after the first audio frame and confirm batch can finish the job.

    This is chapter 6's second verification. The integration must degrade, not raise, so the
    interesting result is that the batch call after the drop still produces audio.
    """
    result: dict = {"dropped_after_bytes": 0, "drop_error": None}

    try:
        async with session.ws_connect(
            f"{WS_URL}?model={voice}",
            headers={"Authorization": f"Token {api_key}"},
            heartbeat=None,
        ) as socket:
            await socket.send_json({"type": "Speak", "text": "".join(TOKEN_CHUNKS)})
            await socket.send_json({"type": "Flush"})
            while True:
                message = await socket.receive()
                if message.type is aiohttp.WSMsgType.BINARY:
                    result["dropped_after_bytes"] = len(message.data)
                    await socket.close(code=1006)
                    break
                if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
    except Exception as err:
        result["drop_error"] = f"{type(err).__name__}: {err}"

    result["fallback"] = await batch_fallback(session, api_key, voice)
    result["degraded_cleanly"] = result["fallback"]["status"] == 200
    return result


def summarize(label: str, values: list[float]) -> str:
    if not values:
        return f"  {label:<16} no samples"
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return (
        f"  {label:<16} median {statistics.median(ordered):>7.1f}  "
        f"min {ordered[0]:>7.1f}  max {ordered[-1]:>7.1f}  p95 {p95:>7.1f}"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10, help="how many socket runs to time")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--label", default="", help="what hardware this is, for the record")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        print(
            "DEEPGRAM_API_KEY is not set. Get one at https://console.deepgram.com", file=sys.stderr
        )
        return 2

    label = args.label or f"{platform.node()} {platform.machine()}"
    print(f"Flux TTS first-frame latency, {args.runs} runs, {args.voice}")
    print(f"Measured on: {label}\n")

    runs: list[Timings] = []
    async with aiohttp.ClientSession() as session:
        for index in range(args.runs):
            timings = await one_run(session, api_key, args.voice)
            runs.append(timings)
            row = timings.as_dict()
            note = f"  ERROR {row['error']}" if row["error"] else ""
            print(
                f"  run {index + 1:>2}  connect {row['connect_ms']}  "
                f"first_frame {row['first_frame_ms']}  metadata {row['metadata_ms']}  "
                f"audio {row['audio_ms']}  rtf {row['realtime_factor']}{note}"
            )

        print("\nbatch, same text, for comparison")
        batch = await batch_fallback(session, api_key, args.voice)
        print(f"  status {batch['status']}  {batch['bytes']} bytes  wall {batch['wall_ms']} ms")

        print("\ndropping the socket mid turn")
        drop = await drop_mid_turn(session, api_key, args.voice)
        verdict = "DEGRADED CLEANLY" if drop["degraded_cleanly"] else "DID NOT DEGRADE"
        print(f"  dropped after {drop['dropped_after_bytes']} bytes -> {verdict}")
        if drop["drop_error"]:
            print(f"  socket raised on close, which is expected: {drop['drop_error']}")

    good = [run for run in runs if run.error is None]
    print(f"\ndistribution over {len(good)} clean runs of {len(runs)} (milliseconds)")
    print(summarize("connect", [r.connect_ms for r in good if r.connect_ms]))
    print(summarize("first frame", [r.first_frame_ms for r in good if r.first_frame_ms]))
    print(summarize("to metadata", [r.metadata_ms for r in good if r.metadata_ms]))

    factors = [r.realtime_factor for r in good if r.realtime_factor]
    if factors:
        median_factor = statistics.median(factors)
        print(f"\n  realtime factor  median {median_factor:.2f}x")
        print(
            "  Above 1.0 means audio arrives faster than it plays, so playback cannot starve."
            if median_factor > 1.0
            else "  At or below 1.0 means playback can starve. Streaming buys nothing here."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hardware": label,
        "voice": args.voice,
        "python": platform.python_version(),
        "chunks": TOKEN_CHUNKS,
        "runs": [run.as_dict() for run in runs],
        "batch": batch,
        "socket_drop": drop,
    }
    target = OUT_DIR / f"first-frame-{time.strftime('%Y%m%d-%H%M%S')}.json"
    target.write_text(json.dumps(record, indent=2))
    print(f"\nwrote {target}")
    print("Quote a number from this file only with the hardware line attached to it.")

    return 0 if good and drop["degraded_cleanly"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
