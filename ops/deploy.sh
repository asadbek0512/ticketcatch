#!/usr/bin/env bash
# Pull the latest commit and restart. Run on the server, by hand or from cron.
#
# GitHub Actions is billing-locked on this account, so deployment is a pull from the server rather
# than a push from CI — same effect, no minutes required.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/ticketcatch}"
BRANCH="${BRANCH:-main}"
cd "$APP_DIR"

git fetch -q origin "$BRANCH"
local_sha=$(git rev-parse HEAD)
remote_sha=$(git rev-parse "origin/$BRANCH")
[ "$local_sha" = "$remote_sha" ] && { echo "already at $local_sha"; exit 0; }

echo "deploying $local_sha -> $remote_sha"
# data/ and .env are gitignored, so the live database and secrets survive the reset.
git reset --hard "origin/$BRANCH"

"$HOME/.local/bin/uv" sync --python 3.11 --quiet
pm2 restart ticketcatch-bot ticketcatch-poll --update-env >/dev/null

echo "deployed $(git log --oneline -1)"
