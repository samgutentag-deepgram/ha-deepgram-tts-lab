#!/usr/bin/env bash
#
# Follow the Home Assistant log, filtered to this integration, so the first
# question after a deploy has a one command answer: did it load.
#
# Bash, not /bin/sh, for the same reasons as deploy.sh.
#
# ---------------------------------------------------------------------------
# CONFIGURATION
#
# Same scheme as deploy.sh, same env file, so one file configures both.
#
#   HA_DEPLOY_ENV_FILE       Path to the env file. Default: .env at the repo root,
#                            or scripts/.ha-deploy.env when that exists.
#
# Required:
#
#   HA_DEPLOY_LOG_SOURCE     Where the log comes from. No default, on purpose.
#                              api  GET /api/error_log over HTTP, polled. Works on
#                                   every install type, needs a token.
#                              ssh  tail -F the log file over ssh. Needs shell
#                                   access to the machine and a log file on disk.
#
# api source:
#
#   HA_DEPLOY_URL            Base URL, for example http://homeassistant.local:8123
#   HA_DEPLOY_TOKEN          Long lived access token
#   HA_DEPLOY_LOG_INTERVAL   Seconds between polls. Default: 3
#
# ssh source:
#
#   HA_DEPLOY_SSH_HOST       Hostname or IP
#   HA_DEPLOY_SSH_USER       Default: root
#   HA_DEPLOY_SSH_PORT       Default: 22
#   HA_DEPLOY_SSH_KEY        Optional identity file
#   HA_DEPLOY_CONFIG_DIR     Default: /config
#   HA_DEPLOY_LOG_FILE       Default: $HA_DEPLOY_CONFIG_DIR/home-assistant.log
#
# Both sources:
#
#   HA_DEPLOY_LOG_FILTER     Extended regex of lines to keep.
#                            Default: deepgram_tts|deepgram|DeepgramError|tts\.
#                            Set it to '.' to see everything.
#   HA_DEPLOY_LOG_LINES      Backlog lines to print before following. Default: 40
#   HA_DEPLOY_LOG_FOLLOW     Set to 0 for one shot: print the backlog and exit.
#                            Useful right after a restart. Default: 1
#
# Note on /api/error_log: it returns the whole log for the current session as one
# plaintext response, not a stream. There is no server side tail. This script polls
# and prints what is new, which is why a restart shows up as the line count
# dropping back to zero.
#
# Usage:
#   scripts/tail_ha_log.sh
#   HA_DEPLOY_LOG_FOLLOW=0 scripts/tail_ha_log.sh
#   HA_DEPLOY_LOG_FILTER='deepgram_tts' scripts/tail_ha_log.sh
# ---------------------------------------------------------------------------

set -euo pipefail

PROG=tail_ha_log

die() {
  printf '%s: error: %s\n' "$PROG" "$*" >&2
  exit 1
}

say() {
  printf '%s\n' "$*"
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# One env file for the whole repo. scripts/.ha-deploy.env still wins if it exists,
# so an older setup keeps working, but .env at the repo root is the documented one.
if [ -n "${HA_DEPLOY_ENV_FILE:-}" ]; then
  ENV_FILE="$HA_DEPLOY_ENV_FILE"
elif [ -f "$SCRIPT_DIR/.ha-deploy.env" ]; then
  ENV_FILE="$SCRIPT_DIR/.ha-deploy.env"
else
  ENV_FILE="$SCRIPT_DIR/../.env"
fi
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

LOG_SOURCE="${HA_DEPLOY_LOG_SOURCE:-}"
HA_URL="${HA_DEPLOY_URL:-}"
HA_TOKEN="${HA_DEPLOY_TOKEN:-}"
INTERVAL="${HA_DEPLOY_LOG_INTERVAL:-3}"
SSH_HOST="${HA_DEPLOY_SSH_HOST:-}"
SSH_USER="${HA_DEPLOY_SSH_USER:-root}"
SSH_PORT="${HA_DEPLOY_SSH_PORT:-22}"
SSH_KEY="${HA_DEPLOY_SSH_KEY:-}"
CONFIG_DIR="${HA_DEPLOY_CONFIG_DIR:-/config}"
LOG_FILE="${HA_DEPLOY_LOG_FILE:-$CONFIG_DIR/home-assistant.log}"
FILTER="${HA_DEPLOY_LOG_FILTER:-deepgram_tts|deepgram|DeepgramError|tts\.}"
BACKLOG="${HA_DEPLOY_LOG_LINES:-40}"
FOLLOW="${HA_DEPLOY_LOG_FOLLOW:-1}"

if [ -z "$LOG_SOURCE" ]; then
  die "HA_DEPLOY_LOG_SOURCE is unset. Set it to 'api' or 'ssh'. There is no default
  because the two need different credentials and guessing wrong just fails slower.
  See the header of this script, or docs/deploying.html."
fi

case "$LOG_SOURCE" in
  api|ssh) ;;
  *) die "HA_DEPLOY_LOG_SOURCE must be 'api' or 'ssh', got '$LOG_SOURCE'" ;;
esac

case "$LOG_SOURCE" in
  api)
    [ -n "$HA_URL" ] || die "HA_DEPLOY_LOG_SOURCE=api needs HA_DEPLOY_URL"
    [ -n "$HA_TOKEN" ] || die "HA_DEPLOY_LOG_SOURCE=api needs HA_DEPLOY_TOKEN"
    command -v curl >/dev/null 2>&1 || die "curl not found on this machine"
    ;;
  ssh)
    [ -n "$SSH_HOST" ] || die "HA_DEPLOY_LOG_SOURCE=ssh needs HA_DEPLOY_SSH_HOST"
    command -v ssh >/dev/null 2>&1 || die "ssh not found on this machine"
    ;;
esac

say "$PROG: source $LOG_SOURCE, filter /$FILTER/, backlog $BACKLOG lines, follow $FOLLOW"

# --- ssh: let tail do the work ----------------------------------------------

if [ "$LOG_SOURCE" = ssh ]; then
  ssh_args=(-p "$SSH_PORT")
  if [ -n "$SSH_KEY" ]; then
    ssh_args+=(-i "$SSH_KEY")
  fi

  if [ "$FOLLOW" = 1 ]; then
    remote="tail -n $BACKLOG -F '$LOG_FILE'"
  else
    remote="tail -n $BACKLOG '$LOG_FILE'"
  fi

  say "$PROG: $SSH_USER@$SSH_HOST:$LOG_FILE"
  say ""
  # grep exits 1 on no match, which under `set -e` would look like a failure.
  ssh "${ssh_args[@]}" "$SSH_USER@$SSH_HOST" "$remote" \
    | grep --line-buffered -E "$FILTER" || true
  exit 0
fi

# --- api: poll /api/error_log and print what is new -------------------------

fetch_log() {
  curl --fail --silent --show-error --max-time 30 \
    -H "Authorization: Bearer $HA_TOKEN" \
    "$HA_URL/api/error_log"
}

say "$PROG: $HA_URL/api/error_log every ${INTERVAL}s"
say ""

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

seen=0
first=1

while :; do
  if ! fetch_log >"$TMP" 2>/dev/null; then
    # One shot has nothing to wait for, so a failed fetch is the answer, not a retry.
    if [ "$FOLLOW" != 1 ]; then
      die "could not fetch $HA_URL/api/error_log. Check HA_DEPLOY_URL and HA_DEPLOY_TOKEN."
    fi
    say "$PROG: fetch failed, retrying in ${INTERVAL}s (a restarting instance looks like this)"
    seen=0
    sleep "$INTERVAL"
    continue
  fi

  total=$(wc -l <"$TMP" | tr -d ' ')

  # A shorter log than last time means the session restarted and /api/error_log
  # started over, so replay from the top rather than printing nothing.
  if [ "$total" -lt "$seen" ]; then
    say "$PROG: log got shorter, treating it as a restart"
    seen=0
  fi

  if [ "$first" = 1 ]; then
    start=$(( total - BACKLOG ))
    if [ "$start" -lt 0 ]; then
      start=0
    fi
    seen=$start
    first=0
  fi

  if [ "$total" -gt "$seen" ]; then
    tail -n +"$(( seen + 1 ))" "$TMP" | grep -E "$FILTER" || true
    seen=$total
  fi

  if [ "$FOLLOW" != 1 ]; then
    break
  fi

  sleep "$INTERVAL"
done
