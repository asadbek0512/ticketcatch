#!/usr/bin/env bash
# Daily database backup, run from cron.
#
# The database is the only thing on the server that cannot be redeployed: watches, price history,
# per-user settings. Copying the file while the bot is writing to it can capture a torn page, so
# this uses sqlite3's own .backup, which takes a consistent snapshot of a live database.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/ticketcatch}"
DB="$APP_DIR/data/ticketcatch.sqlite"
DEST="${BACKUP_DIR:-$HOME/backups/ticketcatch}"
KEEP_DAYS="${KEEP_DAYS:-14}"

[ -f "$DB" ] || { echo "no database at $DB"; exit 1; }
mkdir -p "$DEST"

stamp=$(date -u +%Y%m%d-%H%M)
out="$DEST/ticketcatch-$stamp.sqlite"

sqlite3 "$DB" ".backup '$out'"
gzip -f "$out"

# Keep two weeks; the useful window for "was this route cheaper last month?" is shorter than the
# window in which nobody notices the disk filling up.
find "$DEST" -name 'ticketcatch-*.sqlite.gz' -mtime "+$KEEP_DAYS" -delete

echo "backed up to $out.gz ($(du -h "$out.gz" | cut -f1))"
