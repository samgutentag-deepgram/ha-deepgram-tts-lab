#!/usr/bin/env python3
"""Exercise the real FluxSocket against the live API, and measure what it costs.

`scripts/measure_first_frame.py` is the portable one: stdlib plus aiohttp, opens its own
socket, and runs on a bare Raspberry Pi with nothing installed. Its weakness, found by the
skeptic pass, is that it never imports `stream.py`, so satisfying it produces a real latency
number and validates none of the code the number is about.

This is the other half. It imports `custom_components.deepgram_tts` and drives the actual
`DeepgramClient` and `FluxSocket` the entity uses, so a defect in our client shows up here.
It needs the project venv, which is why it did not replace the portable script.

    .venv/bin/python scripts/live_stream_check.py
    .venv/bin/python scripts/live_stream_check.py --runs 10 --voice flux-haley-en

What it settles that nothing else can:

1. Whether the socket actually emits audio at the rate `WS_SAMPLE_RATE` claims. The WAV header
   this integration prepends is an assertion, not a fact the protocol carries, and
   `FluxSocket._check_sample_rate` compares bytes received against the duration the server
   reported. A mismatch here means playback pitch is wrong in every house that installs this.
2. Whether the WAV the socket produces is decodable by ffmpeg, which is what Home Assistant
   converts with.
3. Whether an expired key is reported as an auth failure rather than a network failure, on the
   socket path, against the real server rather than a fake.
4. Whether dropping the socket mid turn degrades rather than raising.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncGenerator
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aiohttp

from custom_components.deepgram_tts.api import DeepgramClient
from custom_components.deepgram_tts.const import (
    DEFAULT_VOICE,
    WS_BITS_PER_SAMPLE,
    WS_CHANNELS,
    WS_SAMPLE_RATE,
)
from custom_components.deepgram_tts.errors import (
    DeepgramAuthError,
    DeepgramConnectionError,
)

OUT_DIR = Path(__file__).resolve().parent / "out"

# Chunked the way an LLM emits tokens. A single complete sentence would measure something this
# integration never does.
TOKEN_CHUNKS = [
    "The back door ",
    "has been unlocked ",
    "since four this afternoon, ",
    "and the garage light ",
    "is still on.",
]


async def chunks(delay: float = 0.04) -> AsyncGenerator[str]:
    for chunk in TOKEN_CHUNKS:
        yield chunk
        await asyncio.sleep(delay)


def probe(path: Path) -> dict:
    """Ask ffmpeg what it thinks of our WAV, since ffmpeg is what Home Assistant uses."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,sample_rate,channels",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return {"error": f"{type(err).__name__}: {err}"}
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:300]}
    return json.loads(out.stdout or "{}")


async def one_turn(client: DeepgramClient, voice: str, index: int) -> dict:
    socket = client.stream(model=voice)
    body = bytearray()
    started = time.perf_counter()

    async for frame in socket.stream(chunks()):
        body.extend(frame)

    wall_ms = (time.perf_counter() - started) * 1000
    metrics = socket.metrics

    path = OUT_DIR / f"stream-{index:02d}.wav"
    path.write_bytes(bytes(body))

    # The rate the stream actually implies, computed here rather than trusted, so the number is
    # in the report whether or not the client's own check tripped.
    bytes_per_ms = WS_SAMPLE_RATE * WS_CHANNELS * WS_BITS_PER_SAMPLE / 8 / 1000
    implied = None
    if metrics.audio_duration_ms:
        implied = round(
            WS_SAMPLE_RATE * (metrics.audio_bytes / (metrics.audio_duration_ms * bytes_per_ms))
        )

    return {
        "connect_ms": round(metrics.connect_ms or 0, 1),
        "first_frame_ms": round(metrics.first_frame_ms or 0, 1),
        "metadata_ms": round(metrics.metadata_ms or 0, 1),
        "wall_ms": round(wall_ms, 1),
        "audio_duration_ms": metrics.audio_duration_ms,
        "audio_bytes": metrics.audio_bytes,
        "total_bytes": len(body),
        "chunks_sent": metrics.chunks_sent,
        "realtime_factor": round(metrics.realtime_factor, 2) if metrics.realtime_factor else None,
        "implied_sample_rate": implied,
        "warnings": list(metrics.warnings),
        "file": str(path),
    }


async def check_expired_key(voice: str) -> str:
    """Confirm a rejected key reads as auth, not network, against the real server."""
    async with aiohttp.ClientSession() as session:
        client = DeepgramClient(session, "0" * 40)
        socket = client.stream(model=voice)
        try:
            async for _ in socket.stream(chunks(delay=0)):
                pass
        except DeepgramAuthError as err:
            return f"PASS  DeepgramAuthError: {err}"
        except DeepgramConnectionError as err:
            return f"FAIL  reported as a connection error, which hides an expired key: {err}"
        except Exception as err:
            return f"FAIL  {type(err).__name__}: {err}"
        return "FAIL  a bad key produced audio"


async def check_drop_mid_turn(client: DeepgramClient, voice: str) -> str:
    """Abandon the generator mid turn. The socket must close and nothing must hang."""
    socket = client.stream(model=voice)
    generator = socket.stream(chunks(delay=0))
    frames = 0
    try:
        async for _ in generator:
            frames += 1
            if frames >= 3:
                break
        await generator.aclose()
    except Exception as err:
        return f"FAIL  abandoning the generator raised {type(err).__name__}: {err}"

    leaked = [task for task in asyncio.all_tasks() if "_send" in repr(task) and not task.done()]
    if leaked:
        return f"FAIL  {len(leaked)} sender task(s) left running"
    return f"PASS  closed cleanly after {frames} frames, no task leak"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        print("DEEPGRAM_API_KEY is not set. Copy .env.sample to .env, then:", file=sys.stderr)
        print("  set -a && source .env && set +a", file=sys.stderr)
        return 2

    label = args.label or f"{platform.node()} {platform.machine()}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"FluxSocket live check, {args.runs} runs, {args.voice}")
    print(f"Measured on: {label}")
    print(f"Header claims: {WS_SAMPLE_RATE} Hz, {WS_CHANNELS} channel, {WS_BITS_PER_SAMPLE}-bit\n")

    runs: list[dict] = []
    async with aiohttp.ClientSession() as session:
        client = DeepgramClient(session, api_key)

        for index in range(args.runs):
            try:
                row = await one_turn(client, args.voice, index)
            except Exception as err:
                print(f"  run {index + 1:>2}  FAILED {type(err).__name__}: {err}")
                continue
            runs.append(row)
            print(
                f"  run {index + 1:>2}  connect {row['connect_ms']:>7.1f}  "
                f"first_frame {row['first_frame_ms']:>7.1f}  done {row['metadata_ms']:>8.1f}  "
                f"audio {row['audio_duration_ms']}ms  rtf {row['realtime_factor']}  "
                f"rate~{row['implied_sample_rate']}"
            )
            for warning in row["warnings"]:
                print(f"           WARNING {warning}")

        print("\nabandoning a turn mid stream")
        print("  " + await check_drop_mid_turn(client, args.voice))

    print("\nan expired key on the socket")
    print("  " + await check_expired_key(args.voice))

    if not runs:
        print("\nno successful runs")
        return 1

    print(f"\ndistribution over {len(runs)} runs (milliseconds)")
    for name in ("connect_ms", "first_frame_ms", "metadata_ms"):
        values = sorted(row[name] for row in runs)
        p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
        print(
            f"  {name:<16} median {statistics.median(values):>8.1f}  min {values[0]:>8.1f}  "
            f"max {values[-1]:>8.1f}  p95 {p95:>8.1f}"
        )

    rates = {row["implied_sample_rate"] for row in runs}
    print(f"\n  implied sample rate across runs: {sorted(rates)}")
    if rates == {WS_SAMPLE_RATE}:
        print(f"  MATCHES the {WS_SAMPLE_RATE} Hz in the WAV header. Playback pitch is correct.")
    else:
        print(f"  DOES NOT MATCH the header's {WS_SAMPLE_RATE} Hz. Playback pitch will be wrong.")

    print("\nwhat ffmpeg makes of the WAV we produced")
    info = probe(Path(runs[0]["file"]))
    print(f"  {json.dumps(info, separators=(',', ':'))}")

    factors = [row["realtime_factor"] for row in runs if row["realtime_factor"]]
    if factors:
        median = statistics.median(factors)
        print(f"\n  realtime factor median {median:.2f}x")
        print(
            "  Above 1.0, so audio arrives faster than it plays and playback cannot starve."
            if median > 1.0
            else "  At or below 1.0, so playback can starve. Streaming buys nothing here."
        )

    record = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hardware": label,
        "voice": args.voice,
        "note": "Driven through the real DeepgramClient and FluxSocket, not a standalone socket.",
        "header_sample_rate": WS_SAMPLE_RATE,
        "runs": runs,
    }
    target = OUT_DIR / f"live-stream-{time.strftime('%Y%m%d-%H%M%S')}.json"
    target.write_text(json.dumps(record, indent=2))
    print(f"\nwrote {target}")
    print("Quote a number from this file only with the hardware line attached to it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
