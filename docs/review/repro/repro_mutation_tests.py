"""Mutation testing for the claims the ledger makes about the test suite.

    .venv/bin/python docs/review/repro/repro_mutation_tests.py

A test only earns its place if it fails against a broken implementation. This plants specific
breakages, one per claim, and reports whether the suite noticed. It copies the repo to a scratch
tree, so the repo under review is never modified.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path("/Users/samgutentag/LABS/ha-deepgram-tts-lab/.claude/worktrees/agent-a72565c57ade8ce4a")
PYTHON = "/Users/samgutentag/LABS/ha-deepgram-tts-lab/.venv/bin/python"

ORIGINAL_STREAM = """                sender = asyncio.create_task(self._send(socket, chunks))
                try:
                    async for frame in self._receive(socket, first_speak):
                        yield frame
                finally:
                    await self._finish_sender(sender)
"""

SERIALIZED_STREAM = """                sender = asyncio.create_task(self._send(socket, chunks))
                try:
                    await sender
                    async for frame in self._receive(socket, first_speak):
                        yield frame
                finally:
                    await self._finish_sender(sender)
"""


def mutate_and_run(name: str, claim: str, edits: list[tuple[str, str, str]]) -> None:
    """Apply (relative path, find, replace) edits to a scratch copy and run the suite."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        shutil.copytree(
            REPO,
            root,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".claude", "docs"),
        )
        for rel, find, replace in edits:
            path = root / rel
            body = path.read_text(encoding="utf-8")
            if find not in body:
                print(f"SETUP FAIL {name}: pattern not found in {rel}\n")
                return
            path.write_text(body.replace(find, replace, 1), encoding="utf-8")

        proc = subprocess.run(
            [PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
        verdict = "CAUGHT" if proc.returncode != 0 else "MISSED"
        print(f"{verdict}  {name}")
        print(f"        claim: {claim}")
        print(f"        {lines[-1] if lines else '(no output)'}")
        for line in lines:
            if line.startswith("FAILED") or line.startswith("ERROR"):
                print(f"        {line}")
        print()


print(f"python {sys.version.split()[0]}")
print("baseline first, so a MISSED result cannot be a broken harness\n")

mutate_and_run("baseline, nothing mutated", "the suite passes as committed", [])

mutate_and_run(
    "A. send every chunk before reading anything",
    "the first audio frame arrives before the text runs out",
    [("custom_components/deepgram_tts/stream.py", ORIGINAL_STREAM, SERIALIZED_STREAM)],
)

mutate_and_run(
    "A2. buffer the whole message and send it as one Speak",
    "no buffering of the message; the server places the boundaries",
    [
        (
            "custom_components/deepgram_tts/stream.py",
            """        async for chunk in chunks:
            if not chunk:
                continue
            await socket.send_json({"type": "Speak", "text": chunk})
            self.metrics.chunks_sent += 1
        await socket.send_json({"type": "Flush"})""",
            """        whole = "".join([chunk async for chunk in chunks])
        if whole:
            await socket.send_json({"type": "Speak", "text": whole})
            self.metrics.chunks_sent += 1
        await socket.send_json({"type": "Flush"})""",
        )
    ],
)

mutate_and_run(
    "A3. split each chunk on commas before sending",
    "no sentence splitting; a regex over the text means the design was not read",
    [
        (
            "custom_components/deepgram_tts/stream.py",
            """            await socket.send_json({"type": "Speak", "text": chunk})
            self.metrics.chunks_sent += 1""",
            """            for piece in chunk.replace(",", ",|").split("|"):
                if piece:
                    await socket.send_json({"type": "Speak", "text": piece})
            self.metrics.chunks_sent += 1""",
        )
    ],
)

mutate_and_run(
    "B. re-encode the returned audio (strip an ID3 tag)",
    "return what the API gave you, never decoded or re-encoded",
    [
        (
            "custom_components/deepgram_tts/api.py",
            "            audio=body,",
            '            audio=body[10:] if body.startswith(b"ID3") else body,',
        )
    ],
)

mutate_and_run(
    "C. split language codes on an underscore, in models.py",
    "split on a hyphen, never an underscore",
    [
        (
            "custom_components/deepgram_tts/models.py",
            'return frozenset(lang.split("-")[0] for lang in self.languages)',
            'return frozenset(lang.split("_")[0] for lang in self.languages)',
        )
    ],
)

mutate_and_run(
    "C2. split language codes on an underscore, in catalog.py",
    "the other place that splits a language code",
    [
        (
            "custom_components/deepgram_tts/catalog.py",
            'return language.split("-")[0].lower()',
            'return language.split("_")[0].lower()',
        )
    ],
)

mutate_and_run(
    "D. drop the family guard from resolve_voice's ladder",
    "a non-English language must never resolve to Flux",
    [
        (
            "custom_components/deepgram_tts/catalog.py",
            """    for voice in candidates:
        if not voice.is_flux:
            return voice""",
            """    for voice in candidates:
        return voice""",
        )
    ],
)

mutate_and_run(
    "D2. drop the language guard from the preferred-voice branch",
    "a stored Flux preference must not follow a Spanish pipeline into /v2/speak",
    [
        (
            "custom_components/deepgram_tts/catalog.py",
            """        elif base not in voice.base_languages:
            _LOGGER.debug("Preferred voice %s cannot speak %s", preferred, language)
        else:
            return voice""",
            """        else:
            return voice""",
        )
    ],
)

mutate_and_run(
    "E. never cancel the sender and never surface its failure",
    "cleanup happens in the finally",
    [
        (
            "custom_components/deepgram_tts/stream.py",
            "                finally:\n                    await self._finish_sender(sender)",
            "                finally:\n                    pass",
        )
    ],
)

mutate_and_run(
    "F. remove the sample-rate self check",
    "the client checks its own math",
    [
        (
            "custom_components/deepgram_tts/stream.py",
            "        self._check_sample_rate()",
            "        pass",
        )
    ],
)

mutate_and_run(
    "G. declare a real byte length in the WAV header instead of the sentinel",
    "a streaming WAV declares an unknown length",
    [
        (
            "custom_components/deepgram_tts/stream.py",
            "_UNKNOWN_LENGTH = 0xFFFFFFFF",
            "_UNKNOWN_LENGTH = 36",
        )
    ],
)

mutate_and_run(
    "H. send sample_rate with encoding=mp3 after all",
    "sample_rate must not be sent when encoding is mp3",
    [
        (
            "custom_components/deepgram_tts/api.py",
            """        if encoding == ENCODING_MP3:
            _LOGGER.debug(
                "Dropping sample_rate=%s: the API rejects it as not applicable to mp3",
                sample_rate,
            )
        else:
            params["sample_rate"] = str(sample_rate)""",
            """        params["sample_rate"] = str(sample_rate)""",
        )
    ],
)

mutate_and_run(
    "I. route every model to /v2/speak",
    "flux-* to v2, everything else to v1",
    [
        (
            "custom_components/deepgram_tts/api.py",
            "        url = URL_SPEAK_FLUX if family == FAMILY_FLUX else URL_SPEAK_AURA",
            "        url = URL_SPEAK_FLUX",
        )
    ],
)

mutate_and_run(
    "J. rewrap every typed error in the broad handler of async_verify_key",
    "reraise typed errors before any broad except Exception",
    [
        (
            "custom_components/deepgram_tts/api.py",
            """        except DeepgramError:
            # Above the broad handler on purpose. Rewrapping these is what made the codebase
            # this project replaces undebuggable: an expired key read as a dead network.
            raise
        except Exception as err:""",
            """        except Exception as err:""",
        )
    ],
)

mutate_and_run(
    "K. let a catalog fetch failure escape as a raw aiohttp error",
    "raise ConfigEntryNotReady, never a raw aiohttp error",
    [
        (
            "custom_components/deepgram_tts/catalog.py",
            """    except (ClientError, TimeoutError) as err:
        raise DeepgramConnectionError(
            f"Could not read the Deepgram voice catalogs at {URL_MODELS_FLUX} "
            f"and {URL_MODELS_AURA}: {err}"
        ) from err""",
            """    except (ValueError,) as err:
        raise DeepgramConnectionError("unreachable") from err""",
        )
    ],
)
