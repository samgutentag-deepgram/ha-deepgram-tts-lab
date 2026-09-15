#!/usr/bin/env python3
"""Chapter 2 verification against the live Deepgram API, in one command.

HANDOFF section 6.1 asks for one authenticated round trip against both /v1/speak and /v2/speak.
This does that, writes the audio to scripts/out/ so a human can play it, and checks the two
public catalogs against the counts recorded in HANDOFF section 3.3.

Standalone on purpose: stdlib plus aiohttp, no Home Assistant, no custom_components import. It
runs on a laptop with nothing installed but the venv.

Usage:
    DEEPGRAM_API_KEY=... python3 scripts/live_check.py

The catalog half needs no key and always runs. Without a key the script exits 2 before the
authenticated half.
"""

from __future__ import annotations

import asyncio
from collections import Counter
import os
from pathlib import Path
import sys
import time

import aiohttp

HOST = "https://api.deepgram.com"
OUT_DIR = Path(__file__).resolve().parent / "out"

SENTENCE = "Your appointment is confirmed for three o'clock tomorrow."

# (label, url, model, filename)
SPEAK_CASES = [
    ("flux  /v2/speak", f"{HOST}/v2/speak", "flux-haley-en", "flux-haley-en"),
    ("aura  /v1/speak", f"{HOST}/v1/speak", "aura-2-thalia-en", "aura-2-thalia-en"),
]

# From HANDOFF section 3.3, verified live 2026-09-15.
EXPECTED_FLUX_VOICES = 36
EXPECTED_AURA_TTS = 102

TIMEOUT = aiohttp.ClientTimeout(total=60)


async def fetch_catalog(session: aiohttp.ClientSession, url: str) -> dict:
    """Fetch one public model catalog."""
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


async def check_catalogs(session: aiohttp.ClientSession) -> bool:
    """Compare the live catalog counts against the recorded ones."""
    print("catalogs (no auth required)")
    ok = True

    for label, url, expected in (
        ("/v2/models flux tts", f"{HOST}/v2/models", EXPECTED_FLUX_VOICES),
        ("/v1/models aura tts", f"{HOST}/v1/models", EXPECTED_AURA_TTS),
    ):
        try:
            payload = await fetch_catalog(session, url)
        except (TimeoutError, aiohttp.ClientError) as err:
            print(f"  {label}: FAILED to fetch: {err}")
            ok = False
            continue

        voices = payload.get("tts", [])
        count = len(voices)
        families = Counter(voice.get("architecture", "unknown") for voice in voices)
        breakdown = ", ".join(f"{name}={n}" for name, n in sorted(families.items()))
        verdict = "matches HANDOFF" if count == expected else f"DRIFTED from {expected}"
        print(f"  {label}: {count} entries ({breakdown}) -> {verdict}")
        if count != expected:
            ok = False

    return ok


async def check_speak(session: aiohttp.ClientSession, api_key: str) -> bool:
    """Round trip one sentence through both speak endpoints and save the audio."""
    print("\nsynthesis (authenticated)")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
    ok = True

    for label, url, model, stem in SPEAK_CASES:
        started = time.monotonic()
        try:
            async with session.post(
                url, params={"model": model}, json={"text": SENTENCE}, headers=headers
            ) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "(none)")
                body = await response.read()
        except (TimeoutError, aiohttp.ClientError) as err:
            print(f"  {label} {model}: FAILED: {err}")
            ok = False
            continue

        elapsed = time.monotonic() - started
        head = body[:4].hex(" ") or "(empty)"

        if status != 200:
            snippet = body.decode("utf-8", errors="replace")[:200]
            print(f"  {label} {model}: HTTP {status} in {elapsed:.2f}s -> {snippet}")
            ok = False
            continue

        # No extension guessing here. The header is printed so a human judges the container,
        # and the first four bytes confirm it: 49 44 33 is ID3, 52 49 46 46 is RIFF.
        path = OUT_DIR / f"{stem}.bin"
        path.write_bytes(body)
        print(
            f"  {label} {model}: HTTP {status}, {content_type}, {len(body)} bytes, "
            f"{elapsed:.2f}s, first4={head} -> {path.relative_to(OUT_DIR.parent.parent)}"
        )

    return ok


async def main() -> int:
    """Run the catalog checks, then the authenticated round trips."""
    api_key = os.environ.get("DEEPGRAM_API_KEY")

    # The catalog half runs first even with no key, because it is the half that can run
    # unattended and it is the only part that has ever been verified without one.
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        catalogs_ok = await check_catalogs(session)

        if not api_key:
            print(
                "\nDEEPGRAM_API_KEY is not set, so the synthesis half was skipped. "
                "Export a key and rerun.",
                file=sys.stderr,
            )
            return 2

        speak_ok = await check_speak(session, api_key)

    passed = catalogs_ok and speak_ok
    print("\n" + "=" * 64)
    print(f"catalogs:  {'PASS' if catalogs_ok else 'FAIL'}")
    print(f"synthesis: {'PASS' if speak_ok else 'FAIL'}")
    print(f"chapter 2 live check: {'PASS' if passed else 'FAIL'}")
    print("=" * 64)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
