I have odoo production   and 2  staging  clone from production on cloudpepper,  staging 1  database can be  replication from production,  for staging up to date  now I was  used auto buckup and restore to staging ,  for staging 1 I wan to sync  daily with production , how can I implement my system,

5:56 PM

Searched the web
Searched the web
Good research done. Now I have everything needed to give a complete, practical answer. Let me build the architecture diagram and the full implementation.



Here's the complete implementation for your daily sync from production to Staging 1.

Overview of the approach
Since Cloudpepper's API is only available on the Agency plan, the most reliable method for all plans is a bash script running via cron directly on your server via SSH. The 4 steps are: dump production DB → sync filestore → restore to staging → neutralize (disable emails/crons/webhooks).

Step 1 — Create the sync script on your server
SSH into your Cloudpepper server and create the script:

bash
sudo nano /opt/odoo-sync/sync_staging1.sh
Paste this full script:

bash
#!/bin/bash
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────
PROD_DB="your_production_db"
STAGING_DB="your_staging1_db"

PROD_FILESTORE="/var/lib/odoo/filestore/${PROD_DB}"
STAGING_FILESTORE="/var/lib/odoo/filestore/${STAGING_DB}"

BACKUP_DIR="/opt/odoo-sync/backups"
DUMP_FILE="${BACKUP_DIR}/prod_dump_$(date +%Y%m%d).dump"
LOG_FILE="/opt/odoo-sync/logs/sync_$(date +%Y%m%d).log"

ODOO_USER="odoo"
PG_USER="odoo"

# ── Setup ───────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR" "$(dirname $LOG_FILE)"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "===== Sync started: $(date) ====="

# ── Step 1: Dump production database ───────────────────────────
echo "[1/4] Dumping production database..."
sudo -u postgres pg_dump \
    --format=custom \
    --no-acl \
    --no-owner \
    --compress=6 \
    -f "$DUMP_FILE" \
    "$PROD_DB"
echo "      Dump complete: $(du -sh $DUMP_FILE | cut -f1)"

# ── Step 2: Sync filestore ──────────────────────────────────────
echo "[2/4] Syncing filestore..."
sudo -u "$ODOO_USER" rsync -a --delete \
    "${PROD_FILESTORE}/" \
    "${STAGING_FILESTORE}/"
echo "      Filestore synced."

# ── Step 3: Drop and restore staging database ───────────────────
echo "[3/4] Restoring to staging database..."

# Stop staging Odoo to release DB connections
sudo systemctl stop "odoo-${STAGING_DB}" 2>/dev/null || true

# Drop and recreate staging DB
sudo -u postgres dropdb --if-exists "$STAGING_DB"
sudo -u postgres createdb -O "$PG_USER" "$STAGING_DB"

# Restore
sudo -u postgres pg_restore \
    --no-acl \
    --no-owner \
    -d "$STAGING_DB" \
    "$DUMP_FILE"
echo "      Restore complete."

# ── Step 4: Neutralize staging ──────────────────────────────────
echo "[4/4] Neutralizing staging database..."
sudo -u postgres psql "$STAGING_DB" << 'SQL'

-- Disable all outgoing email
UPDATE ir_mail_server SET active = false;
UPDATE fetchmail_server SET active = false;

-- Disable all scheduled actions (crons)
UPDATE ir_cron SET active = false;

-- Disable payment providers
UPDATE payment_provider SET state = 'disabled' WHERE state = 'enabled';

-- Disable webhooks / external actions
UPDATE base_automation SET active = false
  WHERE trigger IN ('on_write','on_create','on_unlink');

-- Mark DB as neutralized
INSERT INTO ir_config_parameter (key, value)
VALUES ('database.is_neutralized', 'True')
ON CONFLICT (key) DO UPDATE SET value = 'True';

-- Change staging URL to avoid confusion
UPDATE ir_config_parameter
SET value = 'https://staging1.your-domain.com'
WHERE key = 'web.base.url';

SQL
echo "      Neutralization complete."

# Restart staging Odoo
sudo systemctl start "odoo-${STAGING_DB}" 2>/dev/null || true

# ── Cleanup old dumps (keep 3 days) ────────────────────────────
find "$BACKUP_DIR" -name "prod_dump_*.dump" -mtime +3 -delete
echo "      Old dumps cleaned."

echo "===== Sync finished: $(date) ====="
Make it executable:

bash
sudo chmod +x /opt/odoo-sync/sync_staging1.sh
Step 2 — Find your exact DB and service names
On Cloudpepper, your DB names and service names depend on your setup. Check them first:

bash
# List all PostgreSQL databases
sudo -u postgres psql -l

# List running Odoo services
sudo systemctl list-units | grep odoo
Update PROD_DB, STAGING_DB, and the systemctl service names in the script to match.

Step 3 — Schedule with cron
bash
sudo crontab -e -u root
Add this line to run every day at 2:00 AM (low traffic time):

cron
0 2 * * * /opt/odoo-sync/sync_staging1.sh >> /opt/odoo-sync/logs/cron.log 2>&1
Step 4 — Test it manually first
Always run once by hand before relying on the cron:

bash
sudo /opt/odoo-sync/sync_staging1.sh
Watch the log:

bash
tail -f /opt/odoo-sync/logs/sync_$(date +%Y%m%d).log
Step 5 — Optional email alert on failure
Add this at the top of the script after the config section:

bash
ALERT_EMAIL="your@email.com"

# Trap errors and send email
trap 'echo "Sync FAILED at line $LINENO. Check log: $LOG_FILE" | \
  mail -s "Odoo staging sync FAILED $(date +%Y-%m-%d)" "$ALERT_EMAIL"' ERR
Summary of what gets synced
Component	Synced	How
Database (all records)	Yes	pg_dump + pg_restore
Filestore (attachments, images)	Yes	rsync
Emails	Disabled	Neutralize step
Scheduled crons	Disabled	Neutralize step
Payment providers	Disabled	Neutralize step
Custom modules	No (already cloned)	No action needed
This is the same approach that Cloudpepper's own neutralized restore feature uses — it disables external communications like emails, webhooks, and payment providers so staging is safe to test without impacting live systems. Your script does the same thing programmatically on a daily schedule. 
Cloudpepper

Let me know if you want to add Slack/Line notifications, or help with the exact service names for your Cloudpepper setup!

