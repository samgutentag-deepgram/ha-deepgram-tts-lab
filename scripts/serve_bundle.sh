#!/usr/bin/env bash
#
# Copy the integration to Home Assistant with no add-on and no SSH.
#
# Your Pi has ports 22, 22222, 445 and 139 closed, so there is no rsync and no Samba.
# What it does have is Studio Code Server, which includes a terminal that can reach this
# laptop over the LAN. So: tar the integration here, serve it on one port for one
# download, and pull it from that terminal.
#
# Two commands total, instead of hand-copying ten files into a browser editor.
#
# Usage:
#
#   ./scripts/serve_bundle.sh
#
# It prints the exact line to paste into the Studio Code Server terminal, waits for the
# download, and shuts the server down. Nothing is left listening.
#
#   PORT=8000        Port to serve on. Default 8000.
#   TIMEOUT=300      Seconds to wait before giving up. Default 300.
#
# Bash, not sh: `set -o pipefail` is not POSIX.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$REPO_DIR/custom_components/deepgram_tts"
PORT="${PORT:-8000}"
TIMEOUT="${TIMEOUT:-300}"

say() { printf '%s\n' "$*"; }
die() { printf 'serve_bundle: error: %s\n' "$*" >&2; exit 1; }

# The same guard deploy.sh has. A wrong path must not produce a tarball of the wrong tree.
[ -f "$SOURCE_DIR/manifest.json" ] || die "no manifest.json in $SOURCE_DIR, refusing to bundle"

VERSION="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$SOURCE_DIR/manifest.json" | head -1)"

# The LAN address the Pi has to reach. Loopback would be useless here.
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
[ -n "$LAN_IP" ] || die "could not find this machine's LAN address; set LAN_IP yourself"

WORK_DIR="$(mktemp -d)"
BUNDLE="$WORK_DIR/deepgram_tts.tar.gz"
trap 'rm -rf "$WORK_DIR"; [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true' EXIT

# -C so the archive contains custom_components/deepgram_tts/... and extracts straight into
# /config. No leading ./ and no absolute paths, so tar cannot write outside the target.
tar -czf "$BUNDLE" -C "$REPO_DIR" \
  --exclude='__pycache__' --exclude='*.pyc' \
  custom_components/deepgram_tts

SIZE="$(du -h "$BUNDLE" | cut -f1)"
CHECKSUM="$(shasum -a 256 "$BUNDLE" | cut -c1-16)"

(cd "$WORK_DIR" && python3 -m http.server "$PORT" --bind 0.0.0.0 >/dev/null 2>&1) &
SERVER_PID=$!
sleep 1
kill -0 "$SERVER_PID" 2>/dev/null || die "could not start a server on port $PORT; try PORT=8001"

say ""
say "deepgram_tts $VERSION bundled, $SIZE, sha256 starts $CHECKSUM"
say ""
say "1. Open Studio Code Server in Home Assistant."
say "2. Terminal menu, New Terminal."
say "3. Paste this one line:"
say ""
say "   cd /config && curl -sSfO http://$LAN_IP:$PORT/deepgram_tts.tar.gz && tar -xzf deepgram_tts.tar.gz && rm deepgram_tts.tar.gz && ls -la custom_components/deepgram_tts"
say ""
say "4. Then restart Home Assistant: Developer tools, YAML tab, Restart."
say "   A restart is required. Python that is already imported does not change without one."
say ""
say "Waiting up to ${TIMEOUT}s for the download. Ctrl-C to stop early."
say ""

# The http.server writes its access log to stderr, which is discarded above, so the
# download is detected by watching for the connection instead of by parsing a log.
elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  if netstat -an 2>/dev/null | grep -q "\.$PORT .*ESTABLISHED"; then
    say "serve_bundle: a client connected. Give it a second, then check the terminal output."
    sleep 3
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

if [ "$elapsed" -ge "$TIMEOUT" ]; then
  say "serve_bundle: nothing connected in ${TIMEOUT}s. The server is shutting down."
  say "serve_bundle: if the Pi could not reach http://$LAN_IP:$PORT, check that this Mac"
  say "serve_bundle: and the Pi are on the same network and that macOS is not firewalling"
  say "serve_bundle: incoming connections (System Settings, Network, Firewall)."
fi

say ""
say "serve_bundle: done, server stopped, nothing left listening."
