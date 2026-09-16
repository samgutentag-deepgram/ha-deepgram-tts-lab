#!/usr/bin/env bash
#
# Run a throwaway Home Assistant on this machine with the integration installed, drive the real
# config flow, synthesize in every supported language, and play the result.
#
# This is the closest thing to the Raspberry Pi that exists without the Raspberry Pi. It is a
# real Home Assistant, the real config flow over the real HTTP API, the real tts manager, and
# real Deepgram. Only the hardware and the network are different.
#
# What it is NOT: a latency benchmark for the Pi, and not a test of any playback device. Numbers
# from here belong to this Mac.
#
#   ./scripts/local_ha.sh            # set up, verify, leave it running
#   ./scripts/local_ha.sh --stop     # stop it and delete the config
#
# Requires DEEPGRAM_API_KEY in the environment:
#
#   set -a && source .env && set +a
#
# Bash, not sh: arrays and pipefail are not POSIX.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HA_DIR="${LOCAL_HA_DIR:-${TMPDIR:-/tmp}/deepgram-tts-local-ha}"
PORT="${LOCAL_HA_PORT:-8124}"
BASE="http://127.0.0.1:$PORT"
VENV_PY="$REPO_DIR/.venv/bin/python"
HASS="$REPO_DIR/.venv/bin/hass"
PASSWORD="local-only-not-a-secret"

say() { printf '%s\n' "$*"; }
die() { printf 'local_ha: error: %s\n' "$*" >&2; exit 1; }
api() { curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }

if [ "${1:-}" = "--stop" ]; then
  pkill -f "hass -c $HA_DIR" 2>/dev/null && say "stopped" || say "nothing was running"
  rm -rf "$HA_DIR"
  say "removed $HA_DIR"
  exit 0
fi

[ -x "$HASS" ] || die "no hass in the venv. uv venv --python 3.14 .venv && uv pip install -r requirements-test.txt"
[ -n "${DEEPGRAM_API_KEY:-}" ] || die "DEEPGRAM_API_KEY is not set. set -a && source .env && set +a"

pkill -f "hass -c $HA_DIR" 2>/dev/null || true
rm -rf "$HA_DIR"
mkdir -p "$HA_DIR/custom_components"

# A symlink, not a copy, so an edit here is live on the next restart and there is never a stale
# second copy of the integration to debug against.
ln -s "$REPO_DIR/custom_components/deepgram_tts" "$HA_DIR/custom_components/deepgram_tts"

cat > "$HA_DIR/configuration.yaml" <<YAML
# Throwaway instance for local verification. Not the Pi.
default_config:

logger:
  default: warning
  logs:
    custom_components.deepgram_tts: debug

http:
  server_port: $PORT
YAML

say "starting Home Assistant on $BASE (first boot installs requirements, give it a minute)"
"$HASS" -c "$HA_DIR" --log-file "$HA_DIR/home-assistant.log" >/dev/null 2>&1 &

# The API answers well before config entries are set up, so waiting on /api/ and then calling
# tts returns "Provider not found" and looks like a broken integration. Wait for onboarding,
# then later wait for the entity itself.
curl -s --retry 60 --retry-delay 3 --retry-all-errors --retry-connrefused -m 5 \
  -o /dev/null "$BASE/api/onboarding" || die "Home Assistant never came up on $PORT"

say "onboarding"
CODE="$(curl -s -X POST "$BASE/api/onboarding/users" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$BASE/\",\"name\":\"Local Test\",\"username\":\"localtest\",\"password\":\"$PASSWORD\",\"language\":\"en\"}" \
  | "$VENV_PY" -c 'import sys,json; print(json.load(sys.stdin).get("auth_code",""))')"
[ -n "$CODE" ] || die "onboarding did not return an auth code"

TOKEN="$(curl -s -X POST "$BASE/auth/token" \
  -d grant_type=authorization_code -d "code=$CODE" -d "client_id=$BASE/" \
  | "$VENV_PY" -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))')"
[ -n "$TOKEN" ] || die "could not exchange the auth code for a token"
printf '%s' "$TOKEN" > "$HA_DIR/token"

say "driving the config flow"
FLOW="$(api -X POST "$BASE/api/config/config_entries/flow" \
  -d '{"handler":"deepgram_tts","show_advanced_options":false}' \
  | "$VENV_PY" -c 'import sys,json; print(json.load(sys.stdin)["flow_id"])')"

# A deliberately bad key first, because the error mapping is worth proving and a flow that only
# ever sees a good key has never exercised it.
BAD="$(api -X POST "$BASE/api/config/config_entries/flow/$FLOW" \
  -d '{"api_key":"0000000000000000000000000000000000000000"}' \
  | "$VENV_PY" -c 'import sys,json; print(json.load(sys.stdin).get("errors",{}).get("base"))')"
if [ "$BAD" = "invalid_auth" ]; then
  say "  a rejected key maps to invalid_auth"
else
  say "  UNEXPECTED: a rejected key produced $BAD, not invalid_auth"
fi

api -X POST "$BASE/api/config/config_entries/flow/$FLOW" \
  -d "{\"api_key\":\"$DEEPGRAM_API_KEY\"}" >/dev/null
TITLE="$(api -X POST "$BASE/api/config/config_entries/flow/$FLOW" -d '{"voice":"flux-haley-en"}' \
  | "$VENV_PY" -c 'import sys,json; d=json.load(sys.stdin); print(d.get("title",""))')"
[ -n "$TITLE" ] || die "the config flow did not create an entry"
say "  created: $TITLE"

say "waiting for the entity, which is the real readiness signal"
ENTITY=""
for _ in $(seq 1 40); do
  ENTITY="$(api "$BASE/api/states" | "$VENV_PY" -c '
import sys,json
ids=[s["entity_id"] for s in json.load(sys.stdin) if s["entity_id"].startswith("tts.deepgram")]
print(ids[0] if ids else "")')"
  [ -n "$ENTITY" ] && break
  curl -s -o /dev/null -m 2 "$BASE/api/" || true
done
[ -n "$ENTITY" ] || die "the tts entity never appeared"
say "  $ENTITY"

say "synthesizing in every supported language"
for LANG_CODE in en es de fr it ja nl; do
  STATUS="$(api -o /dev/null -w '%{http_code}' -X POST "$BASE/api/tts_get_url" \
    -d "{\"engine_id\":\"$ENTITY\",\"message\":\"Checking the language routing for $LANG_CODE right now.\",\"language\":\"$LANG_CODE\",\"cache\":false}")"
  printf '  %-3s HTTP %s\n' "$LANG_CODE" "$STATUS"
done

say "and a language nothing in the catalog speaks, which must fail"
STATUS="$(api -o /dev/null -w '%{http_code}' -X POST "$BASE/api/tts_get_url" \
  -d "{\"engine_id\":\"$ENTITY\",\"message\":\"Isto deve falhar.\",\"language\":\"pt\",\"cache\":false}")"
printf '  pt  HTTP %s%s\n' "$STATUS" "$([ "$STATUS" = "500" ] && echo '  (correct)' || echo '  UNEXPECTED, pt should be refused')"

say ""
say "what the integration actually sent, per call:"
grep "Synthesizing" "$HA_DIR/home-assistant.log" | sed 's/.*deepgram_tts.tts\] /  /' || true

say ""
say "playing the English one"
URL_PATH="$(api -X POST "$BASE/api/tts_get_url" \
  -d "{\"engine_id\":\"$ENTITY\",\"message\":\"The back door has been unlocked since four this afternoon.\",\"cache\":false}" \
  | "$VENV_PY" -c 'import sys,json; print(json.load(sys.stdin)["path"])')"
curl -s -o "$HA_DIR/spoken.mp3" "$BASE$URL_PATH"
if command -v afplay >/dev/null; then
  afplay "$HA_DIR/spoken.mp3" && say "  played"
else
  say "  saved to $HA_DIR/spoken.mp3 (no afplay on this machine)"
fi

say ""
say "still running: $BASE   user localtest   password $PASSWORD"
say "log:  tail -f $HA_DIR/home-assistant.log"
say "stop: $0 --stop"
