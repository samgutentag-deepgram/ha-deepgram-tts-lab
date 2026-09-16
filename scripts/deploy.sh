#!/usr/bin/env bash
#
# Copy custom_components/deepgram_tts to a Home Assistant instance, then restart or
# reload it. Written for the chapter 5 gate in HANDOFF.md section 6: a working batch
# path on real hardware before any streaming work starts.
#
# Bash, not /bin/sh. `set -o pipefail` and arrays are not POSIX, and both are worth
# more here than portability to dash.
#
# ---------------------------------------------------------------------------
# CONFIGURATION
#
# Every variable is read from the environment. An optional env file is sourced
# first, so nothing secret has to live in a shell history. That file is gitignored.
#
#   HA_DEPLOY_ENV_FILE      Path to the env file. Default: .env at the repo root,
#                           or scripts/.ha-deploy.env when that exists.
#
# Required:
#
#   HA_DEPLOY_TRANSPORT     How the files get there. No default, on purpose.
#                             rsync  rsync over ssh to a remote instance
#                             local  plain copy into a directory on this machine,
#                                    for a Container install whose /config is a
#                                    bind mount from this host
#
# Destination, both transports:
#
#   HA_DEPLOY_CONFIG_DIR    The Home Assistant configuration directory. For rsync
#                           this is the path on the far side. For local it is the
#                           host side of the bind mount. Default: /config
#
# rsync transport only:
#
#   HA_DEPLOY_SSH_HOST      Hostname or IP. Required when transport is rsync.
#   HA_DEPLOY_SSH_USER      Default: root
#   HA_DEPLOY_SSH_PORT      Default: 22. The Home Assistant OS host shell is on
#                           22222; the SSH app is on 22.
#   HA_DEPLOY_SSH_KEY       Optional identity file passed to ssh -i.
#
# Restart, both transports, all optional:
#
#   HA_DEPLOY_URL           Base URL of the instance, for example
#                           http://homeassistant.local:8123. Required only when
#                           HA_DEPLOY_TOKEN is set.
#   HA_DEPLOY_TOKEN         Long lived access token from the HA user profile page.
#                           When unset, the copy still happens and the restart step
#                           is skipped with a message.
#   HA_DEPLOY_RESTART       restart | reload | none. Default: restart
#                             restart  POST homeassistant.restart. The only thing
#                                      that reliably picks up changed Python.
#                             reload   POST homeassistant.reload_config_entry.
#                                      Re-runs setup against the ALREADY IMPORTED
#                                      module. See docs/deploying.html; this does
#                                      not pick up edited Python.
#                             none     copy only.
#   HA_DEPLOY_ENTRY_ID      Config entry id, required when RESTART is reload.
#
# Safety:
#
#   HA_DEPLOY_ALLOW_DELETE  Set to 1 to pass --delete to rsync. Off by default.
#                           DANGER: --delete removes files on the destination that
#                           are absent from the source. A wrong HA_DEPLOY_CONFIG_DIR
#                           plus --delete deletes someone else's integration, and
#                           there is no undo on the far side. Only turn this on when
#                           a renamed or removed module is actually stranding a
#                           stale .py that HA keeps importing.
#   HA_DEPLOY_DRY_RUN       Set to 1 to print the plan and the rsync dry run without
#                           writing anything or calling the API.
#
# Usage:
#   scripts/deploy.sh
#   HA_DEPLOY_DRY_RUN=1 scripts/deploy.sh
# ---------------------------------------------------------------------------

set -euo pipefail

PROG=deploy

die() {
  printf '%s: error: %s\n' "$PROG" "$*" >&2
  exit 1
}

say() {
  printf '%s\n' "$*"
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE_DIR="$REPO_ROOT/custom_components/deepgram_tts"

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
  say "$PROG: reading $ENV_FILE"
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

TRANSPORT="${HA_DEPLOY_TRANSPORT:-}"
CONFIG_DIR="${HA_DEPLOY_CONFIG_DIR:-/config}"
SSH_HOST="${HA_DEPLOY_SSH_HOST:-}"
SSH_USER="${HA_DEPLOY_SSH_USER:-root}"
SSH_PORT="${HA_DEPLOY_SSH_PORT:-22}"
SSH_KEY="${HA_DEPLOY_SSH_KEY:-}"
HA_URL="${HA_DEPLOY_URL:-}"
HA_TOKEN="${HA_DEPLOY_TOKEN:-}"
RESTART_MODE="${HA_DEPLOY_RESTART:-restart}"
ENTRY_ID="${HA_DEPLOY_ENTRY_ID:-}"
ALLOW_DELETE="${HA_DEPLOY_ALLOW_DELETE:-0}"
DRY_RUN="${HA_DEPLOY_DRY_RUN:-0}"

# --- validate ---------------------------------------------------------------

# The guard that stops a typo'd path from becoming a destructive rsync. If this
# directory is not the integration, do not touch the far side at all.
[ -d "$SOURCE_DIR" ] || die "source directory not found: $SOURCE_DIR"
[ -f "$SOURCE_DIR/manifest.json" ] || die "no manifest.json in $SOURCE_DIR, refusing to copy"

if [ -z "$TRANSPORT" ]; then
  die "HA_DEPLOY_TRANSPORT is unset. Set it to 'rsync' or 'local'. There is no
  default because guessing wrong writes files to the wrong machine. See the header
  of this script, or docs/deploying.html."
fi

case "$TRANSPORT" in
  rsync|local) ;;
  *) die "HA_DEPLOY_TRANSPORT must be 'rsync' or 'local', got '$TRANSPORT'" ;;
esac

case "$RESTART_MODE" in
  restart|reload|none) ;;
  *) die "HA_DEPLOY_RESTART must be 'restart', 'reload' or 'none', got '$RESTART_MODE'" ;;
esac

if [ "$RESTART_MODE" = reload ] && [ -n "$HA_TOKEN" ] && [ -z "$ENTRY_ID" ]; then
  die "HA_DEPLOY_RESTART=reload needs HA_DEPLOY_ENTRY_ID"
fi

if [ -n "$HA_TOKEN" ] && [ -z "$HA_URL" ]; then
  die "HA_DEPLOY_TOKEN is set but HA_DEPLOY_URL is not"
fi

if [ "$TRANSPORT" = rsync ]; then
  [ -n "$SSH_HOST" ] || die "HA_DEPLOY_TRANSPORT=rsync needs HA_DEPLOY_SSH_HOST"
  command -v rsync >/dev/null 2>&1 || die "rsync not found on this machine"
  command -v ssh >/dev/null 2>&1 || die "ssh not found on this machine"
fi

if [ "$ALLOW_DELETE" = 1 ] && [ "$TRANSPORT" = local ] && ! command -v rsync >/dev/null 2>&1; then
  die "HA_DEPLOY_ALLOW_DELETE=1 with the local transport needs rsync; the cp fallback cannot delete"
fi

VERSION=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SOURCE_DIR/manifest.json" | head -1)
[ -n "$VERSION" ] || die "could not read version from $SOURCE_DIR/manifest.json"

DEST_PARENT="$CONFIG_DIR/custom_components"

# --- say what is about to happen --------------------------------------------

say ""
say "$PROG: plan"
say "  integration    deepgram_tts $VERSION"
say "  source         $SOURCE_DIR"
say "  transport      $TRANSPORT"
if [ "$TRANSPORT" = rsync ]; then
  say "  destination    $SSH_USER@$SSH_HOST:$DEST_PARENT/deepgram_tts (port $SSH_PORT)"
else
  say "  destination    $DEST_PARENT/deepgram_tts"
fi
if [ "$ALLOW_DELETE" = 1 ]; then
  say "  delete         YES, stale files under deepgram_tts will be removed"
else
  say "  delete         no (set HA_DEPLOY_ALLOW_DELETE=1 to change, read the header first)"
fi
if [ -z "$HA_TOKEN" ]; then
  say "  after copy     nothing, HA_DEPLOY_TOKEN is unset"
else
  say "  after copy     $RESTART_MODE via $HA_URL"
fi
if [ "$DRY_RUN" = 1 ]; then
  say "  dry run        YES, nothing will be written"
fi
say ""

# --- copy -------------------------------------------------------------------

START=$(date +%s)
COPY_RESULT="copied"

# No trailing slash on the source, so rsync transfers the deepgram_tts directory
# itself rather than its contents. That also scopes --delete to that one directory
# instead of everything under custom_components.
if [ "$TRANSPORT" = rsync ]; then
  ssh_cmd="ssh -p $SSH_PORT"
  if [ -n "$SSH_KEY" ]; then
    ssh_cmd="$ssh_cmd -i $SSH_KEY"
  fi

  rsync_args=(-rlptD --itemize-changes --human-readable -e "$ssh_cmd")
  if [ "$ALLOW_DELETE" = 1 ]; then
    rsync_args+=(--delete)
  fi
  if [ "$DRY_RUN" = 1 ]; then
    rsync_args+=(--dry-run)
    COPY_RESULT="dry run, nothing written"
  fi

  if [ "$DRY_RUN" = 1 ]; then
    say "$PROG: would run: $ssh_cmd $SSH_USER@$SSH_HOST mkdir -p $DEST_PARENT"
    say "$PROG: rsync (dry run)"
    # A dry run against a destination that does not exist yet is a normal first
    # deploy, and an unreachable host is worth reporting rather than aborting on.
    rsync "${rsync_args[@]}" "$SOURCE_DIR" "$SSH_USER@$SSH_HOST:$DEST_PARENT/" \
      || say "$PROG: dry run could not read the destination. Expected on a first deploy, or the host is unreachable."
  else
    say "$PROG: mkdir -p $DEST_PARENT on $SSH_HOST"
    # shellcheck disable=SC2086
    $ssh_cmd "$SSH_USER@$SSH_HOST" mkdir -p "$DEST_PARENT"
    say "$PROG: rsync"
    rsync "${rsync_args[@]}" "$SOURCE_DIR" "$SSH_USER@$SSH_HOST:$DEST_PARENT/"
  fi
else
  if [ "$DRY_RUN" = 1 ]; then
    COPY_RESULT="dry run, nothing written"
    if [ ! -d "$DEST_PARENT" ]; then
      say "$PROG: $DEST_PARENT does not exist yet, would be created"
      say "$PROG: would copy $SOURCE_DIR to $DEST_PARENT/"
    elif command -v rsync >/dev/null 2>&1; then
      say "$PROG: rsync (dry run)"
      rsync -rlptD --itemize-changes --human-readable --dry-run \
        "$SOURCE_DIR" "$DEST_PARENT/"
    else
      say "$PROG: would copy $SOURCE_DIR to $DEST_PARENT/"
    fi
  else
    mkdir -p "$DEST_PARENT"
    if command -v rsync >/dev/null 2>&1; then
      local_args=(-rlptD --itemize-changes --human-readable)
      if [ "$ALLOW_DELETE" = 1 ]; then
        local_args+=(--delete)
      fi
      say "$PROG: rsync (local)"
      rsync "${local_args[@]}" "$SOURCE_DIR" "$DEST_PARENT/"
    else
      say "$PROG: cp -R (no rsync on this machine)"
      cp -R "$SOURCE_DIR" "$DEST_PARENT/"
    fi
  fi
fi

# --- restart or reload ------------------------------------------------------

RESTART_RESULT="skipped"

ha_post() {
  # $1 service path, $2 JSON body
  curl --fail --silent --show-error --max-time 30 \
    -X POST \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$2" \
    "$HA_URL/api/services/$1" >/dev/null
}

if [ -z "$HA_TOKEN" ]; then
  say ""
  say "$PROG: HA_DEPLOY_TOKEN is unset, so nothing was restarted."
  say "$PROG: restart Home Assistant yourself, or set the token. Python that is"
  say "$PROG: already imported does not change until the process restarts."
  RESTART_RESULT="skipped, no token"
elif [ "$RESTART_MODE" = none ]; then
  RESTART_RESULT="skipped, HA_DEPLOY_RESTART=none"
elif [ "$DRY_RUN" = 1 ]; then
  RESTART_RESULT="skipped, dry run"
else
  command -v curl >/dev/null 2>&1 || die "curl not found on this machine"
  case "$RESTART_MODE" in
    restart)
      say ""
      say "$PROG: POST homeassistant.restart"
      ha_post "homeassistant/restart" '{}'
      RESTART_RESULT="restart requested"
      ;;
    reload)
      say ""
      say "$PROG: POST homeassistant.reload_config_entry entry_id=$ENTRY_ID"
      say "$PROG: note, this re-runs setup against the module HA already imported."
      ha_post "homeassistant/reload_config_entry" "{\"entry_id\":\"$ENTRY_ID\"}"
      RESTART_RESULT="config entry reloaded"
      ;;
  esac
fi

# --- one line, so the outcome is readable from a scrollback -----------------

ELAPSED=$(( $(date +%s) - START ))
say ""
say "$PROG: deepgram_tts $VERSION -> $TRANSPORT:$DEST_PARENT/deepgram_tts | $COPY_RESULT | $RESTART_RESULT | ${ELAPSED}s"
