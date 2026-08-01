#!/usr/bin/env bash
# Watchdog for the two pm2 processes, run from cron every 15 minutes.
#
# pm2 restarts a crashed process on its own; what it cannot see is a process that is *online* but
# no longer working — a wedged browser, a hung poll, a bot whose long-polling died silently. So
# this checks three things that actually prove the bot is alive: pm2 says online, the poll loop is
# still ticking, and its searches still find prices. It alerts once per failure rather than every
# 15 minutes, because an alert that repeats 96 times a day stops being read — and for the same
# reason each threshold is set above the *normal* quiet period, since a watchdog that cries wolf on
# a healthy bot trains its reader to ignore the one alert that matters.
set -uo pipefail

APP_DIR="${APP_DIR:-$HOME/ticketcatch}"
DB="$APP_DIR/data/ticketcatch.sqlite"
STATE="$APP_DIR/data/.health"
HEARTBEAT="$APP_DIR/data/.poll_heartbeat"
PROCS=("ticketcatch-bot" "ticketcatch-poll")

# The poller ticks every 15 minutes and touches the heartbeat each time; an hour of silence means
# the loop is wedged, not busy.
BEAT_MINUTES="${BEAT_MINUTES:-60}"

# Prices, on the other hand, are only written when someone is due — twice a day, at each user's own
# hour. Long silences there are normal, so this threshold is deliberately far above the 12-hour slot
# gap: it exists to catch "every source has stopped answering", which takes days to be certain of.
STALE_HOURS="${STALE_HOURS:-30}"

# shellcheck disable=SC1090
[ -f "$APP_DIR/.env" ] && set -a && . "$APP_DIR/.env" && set +a

alert() {
  local text="$1"
  local chat="${TELEGRAM_OWNER_ID:-}"
  [ -z "$chat" ] || [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && { echo "$text"; return; }
  curl -sS -m 20 -o /dev/null \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${chat}" \
    --data-urlencode "text=🚨 TicketCatch: ${text}"
}

problems=()

for proc in "${PROCS[@]}"; do
  status=$(pm2 jlist 2>/dev/null | python3 -c "
import json,sys
name=sys.argv[1]
for p in json.load(sys.stdin):
    if p['name'] == name:
        print(p['pm2_env']['status']); break
else:
    print('missing')
" "$proc")
  [ "$status" != "online" ] && problems+=("$proc is $status")
done

if [ -f "$HEARTBEAT" ]; then
  beat_min=$(( ( $(date +%s) - $(stat -c %Y "$HEARTBEAT") ) / 60 ))
  [ "$beat_min" -gt "$BEAT_MINUTES" ] &&
    problems+=("poller hasn't ticked for ${beat_min}min — the loop is wedged")
fi  # no file yet = a build older than the heartbeat, or a poller that never started; pm2 covers that

if [ -f "$DB" ]; then
  age_min=$(python3 - "$DB" <<'PY'
import sqlite3, sys
from datetime import datetime, timezone
try:
    con = sqlite3.connect(sys.argv[1])
    row = con.execute("SELECT MAX(captured_at) FROM pricequote").fetchone()
    watching = con.execute("SELECT COUNT(*) FROM watch WHERE active=1 AND paused=0").fetchone()[0]
    con.close()
    if not row or not row[0] or not watching:
        # Nothing to price means nothing to write: silence is the correct output, not a fault.
        print(-1)
    else:
        seen = datetime.fromisoformat(row[0])
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        print(int((datetime.now(timezone.utc) - seen).total_seconds() // 60))
except Exception as e:
    print(f"err {e}")
PY
)
  case "$age_min" in
    err*) problems+=("database unreadable: ${age_min#err }") ;;
    -1) : ;;  # no quotes yet, or nothing being watched — not a fault
    *) [ "$age_min" -gt $((STALE_HOURS * 60)) ] &&
         problems+=("no new prices for $((age_min / 60))h — the poller is stuck") ;;
  esac
else
  problems+=("database missing at $DB")
fi

if [ ${#problems[@]} -eq 0 ]; then
  # Recovered: say so once, so a silent alert channel isn't mistaken for a healthy bot.
  [ -f "$STATE" ] && { alert "recovered, everything is online again"; rm -f "$STATE"; }
  exit 0
fi

report=$(printf '%s; ' "${problems[@]}")
if [ "$(cat "$STATE" 2>/dev/null)" != "$report" ]; then
  alert "$report"
  echo "$report" > "$STATE"
fi
exit 1
