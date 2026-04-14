# PROCEDURE: NexusOS Daily Memory Backup
**ID**: NEXUS-BACKUP-001
**Version**: 1.0
**Created**: 2026-03-13
**Owner**: Pafi / Lis
**Trigger**: Daily at 03:00 AM (MacM4 local time)
**Category**: Infrastructure / Reliability

---

## 1. OBJECTIVE

Backup automat zilnic al memoriei NexusOS de pe MacM4 pe VPS (89.116.229.189), cu alertă Telegram în caz de eșec.

**Surse backup**:
- `~/.nexus/memory/`
- `~/.claude/projects/`

**Destinație**: VPS `89.116.229.189` — `/backups/nexus/$(date +%Y-%m-%d)/`

---

## 2. PREREQUISITES

- SSH key-based auth configurat: `ssh pafi@89.116.229.189` fără parolă
- `rsync` disponibil pe MacM4 și VPS
- Bot Telegram activ (`@claudemacm4_bot`) cu TELEGRAM_BOT_TOKEN și TELEGRAM_CHAT_ID în env
- Directory `/backups/nexus/` creat pe VPS cu permisiuni write pentru userul `pafi`

---

## 3. SCRIPT: `~/.nexus/scripts/daily-backup.sh`

```bash
#!/usr/bin/env bash
# NexusOS Daily Memory Backup
# Runs at 03:00 AM via LaunchAgent
# Version: 1.0

set -euo pipefail

# ── CONFIG ──────────────────────────────────────────────
VPS_HOST="89.116.229.189"
VPS_USER="pafi"
VPS_DEST="/backups/nexus"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
LOG_FILE="$HOME/.nexus/logs/backup-${DATE}.log"
LOCK_FILE="/tmp/nexus-backup.lock"

SOURCES=(
  "$HOME/.nexus/memory/"
  "$HOME/.claude/projects/"
)

# Telegram config
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# ── FUNCTIONS ────────────────────────────────────────────

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

send_telegram() {
  local message="$1"
  if [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]]; then
    log "WARN: Telegram credentials not set, cannot send alert"
    return
  fi
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$message" \
    -d parse_mode="Markdown" \
    > /dev/null 2>&1 || true
}

alert_failure() {
  local reason="$1"
  local msg="🚨 *NexusOS Backup FAILED* — ${DATE}
Motiv: \`${reason}\`
Host: MacM4 → VPS ${VPS_HOST}
Log: \`${LOG_FILE}\`
⏰ $(date '+%H:%M:%S')"
  log "ERROR: $reason"
  send_telegram "$msg"
}

alert_success() {
  local size="$1"
  local duration="$2"
  local msg="✅ *NexusOS Backup OK* — ${DATE}
Size: ${size}
Durată: ${duration}s
Destinație: \`${VPS_USER}@${VPS_HOST}:${VPS_DEST}/${DATE}/\`"
  log "SUCCESS: Backup completed. Size=${size}, Duration=${duration}s"
  send_telegram "$msg"
}

cleanup() {
  rm -f "$LOCK_FILE"
}

# ── MAIN ─────────────────────────────────────────────────

trap cleanup EXIT
trap 'alert_failure "Script interrupted (SIGTERM/SIGINT)"; exit 1' TERM INT

# Create log dir
mkdir -p "$(dirname "$LOG_FILE")"

log "=== NexusOS Daily Backup START ==="

# Lock check — previne rulări concurente
if [[ -f "$LOCK_FILE" ]]; then
  PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "unknown")
  alert_failure "Lock file exists (PID: $PID). Backup already running?"
  exit 1
fi
echo $$ > "$LOCK_FILE"

# Verify SSH connectivity
log "Verificare SSH conectivitate..."
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "echo ok" > /dev/null 2>&1; then
  alert_failure "SSH connection failed la ${VPS_HOST}"
  exit 1
fi

# Create remote destination directory
log "Creare director destinație pe VPS..."
if ! ssh "${VPS_USER}@${VPS_HOST}" "mkdir -p '${VPS_DEST}/${DATE}'"; then
  alert_failure "Nu s-a putut crea directorul ${VPS_DEST}/${DATE} pe VPS"
  exit 1
fi

# Run rsync for each source
START_TIME=$(date +%s)
FAILED_SOURCES=()

for SRC in "${SOURCES[@]}"; do
  if [[ ! -d "$SRC" ]]; then
    log "WARN: Sursa nu există: $SRC — skipping"
    continue
  fi

  SRC_NAME=$(basename "${SRC%/}")
  log "Backup: $SRC → VPS:${VPS_DEST}/${DATE}/${SRC_NAME}/"

  if ! rsync -az --delete \
    --timeout=120 \
    --exclude='*.tmp' \
    --exclude='*.lock' \
    --exclude='.DS_Store' \
    -e "ssh -o ConnectTimeout=10 -o BatchMode=yes" \
    "$SRC" \
    "${VPS_USER}@${VPS_HOST}:${VPS_DEST}/${DATE}/${SRC_NAME}/" \
    >> "$LOG_FILE" 2>&1; then
    FAILED_SOURCES+=("$SRC")
    log "ERROR: rsync failed pentru $SRC"
  else
    log "OK: $SRC sync'd cu succes"
  fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Check for failures
if [[ ${#FAILED_SOURCES[@]} -gt 0 ]]; then
  alert_failure "rsync eșuat pentru: ${FAILED_SOURCES[*]}"
  exit 1
fi

# Calculate backup size on VPS
BACKUP_SIZE=$(ssh "${VPS_USER}@${VPS_HOST}" "du -sh '${VPS_DEST}/${DATE}' 2>/dev/null | cut -f1" || echo "N/A")

# Rotate old backups — păstrează ultimele 14 zile
log "Rotație backup-uri vechi (păstrare 14 zile)..."
ssh "${VPS_USER}@${VPS_HOST}" "
  find '${VPS_DEST}' -maxdepth 1 -type d -name '20*' | sort | head -n -14 | xargs -r rm -rf
" >> "$LOG_FILE" 2>&1 || log "WARN: Rotația backup-urilor a eșuat (non-fatal)"

alert_success "$BACKUP_SIZE" "$DURATION"
log "=== NexusOS Daily Backup DONE (${DURATION}s) ==="

exit 0
```

---

## 4. LAUNCHAGENT: `~/Library/LaunchAgents/com.nexus.daily-backup.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.nexus.daily-backup</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/pafi/.nexus/scripts/daily-backup.sh</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>3</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key>
    <string>/Users/pafi</string>
    <key>TELEGRAM_BOT_TOKEN</key>
    <string>PLACEHOLDER_REPLACE_WITH_REAL_TOKEN</string>
    <key>TELEGRAM_CHAT_ID</key>
    <string>PLACEHOLDER_REPLACE_WITH_REAL_CHAT_ID</string>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/pafi/.nexus/logs/daily-backup-launchagent.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/pafi/.nexus/logs/daily-backup-launchagent-err.log</string>

  <key>RunAtLoad</key>
  <false/>

  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
```

---

## 5. SETUP — PAȘI DE INSTALARE

### 5.1 Pe VPS (o singură dată)
```bash
ssh pafi@89.116.229.189
mkdir -p /backups/nexus
chmod 700 /backups/nexus
exit
```

### 5.2 Pe MacM4 — Script
```bash
# Copiază scriptul
cp daily-backup.sh ~/.nexus/scripts/daily-backup.sh
chmod +x ~/.nexus/scripts/daily-backup.sh

# Creează directorul de logs
mkdir -p ~/.nexus/logs
```

### 5.3 Pe MacM4 — LaunchAgent
```bash
# 1. Editează plist-ul — înlocuiește PLACEHOLDER cu tokenul și chat_id real
nano ~/Library/LaunchAgents/com.nexus.daily-backup.plist

# 2. Încarc-o
launchctl load ~/Library/LaunchAgents/com.nexus.daily-backup.plist

# 3. Verifică că e loaded
launchctl list | grep nexus.daily-backup
```

### 5.4 Test manual
```bash
# Rulează direct (testare înainte de a activa LaunchAgent)
TELEGRAM_BOT_TOKEN="<token>" TELEGRAM_CHAT_ID="<chat_id>" \
  bash ~/.nexus/scripts/daily-backup.sh

# Verifică log
tail -50 ~/.nexus/logs/backup-$(date +%Y-%m-%d).log

# Verifică pe VPS
ssh pafi@89.116.229.189 "ls -la /backups/nexus/$(date +%Y-%m-%d)/"
```

---

## 6. COMPORTAMENT EXPECTED

| Scenariu | Acțiune script | Alertă Telegram |
|---|---|---|
| Backup reușit | Log SUCCESS, rotație | ✅ mesaj succes cu size + durată |
| SSH down | Exit imediat | 🚨 "SSH connection failed" |
| rsync fail (o sursă) | Continuă cu celelalte | 🚨 cu lista surselor eșuate |
| Lock file prezent | Exit imediat | 🚨 "Backup already running?" |
| Rotație fail | Continuă (non-fatal) | Nicio alertă (warn în log) |
| Sursă lipsă (dir inexistent) | Skip cu WARN | Nicio alertă (non-fatal) |

---

## 7. ROTAȚIE & RETENȚIE

- Backup-urile mai vechi de **14 zile** sunt șterse automat de pe VPS.
- Structura pe VPS:
  ```
  /backups/nexus/
  ├── 2026-03-13/
  │   ├── memory/        ← ~/.nexus/memory/
  │   └── projects/      ← ~/.claude/projects/
  ├── 2026-03-12/
  └── ...
  ```

---

## 8. TROUBLESHOOTING

**Backup nu rulează la 03:00**:
```bash
launchctl list | grep nexus.daily-backup
# Dacă lipsește → launchctl load ~/Library/LaunchAgents/com.nexus.daily-backup.plist
# Dacă MacM4 e în sleep → Energy Saver: dezactivează sleep sau adaugă Power Nap
```

**SSH connection failed**:
```bash
ssh -v pafi@89.116.229.189
# Verifică ~/.ssh/config și known_hosts
# Verifică că cheia publică e în VPS authorized_keys
```

**Alertele Telegram nu vin**:
```bash
# Verifică env vars în plist — PLACEHOLDER-urile trebuie înlocuite cu valorile reale
# Test direct:
curl -s "https://api.telegram.org/bot<TOKEN>/getMe"
```

**Disk space VPS**:
```bash
ssh pafi@89.116.229.189 "df -h /backups"
# Dacă e plin → reduce retenția (head -n -14 → head -n -7)
```

---

## 9. NOTES

- Scriptul folosește `rsync -az --delete` → sincronizare incrementală, eficientă pe bandwidth.
- `set -euo pipefail` asigură că orice eroare neașteptată oprește scriptul (nu continuă în stare inconsistentă).
- Fișierele `.tmp`, `.lock`, `.DS_Store` sunt excluse explicit din backup.
- Alertele de succes sunt opționale — pot fi dezactivate dacă sunt prea verbose (comentează linia `alert_success`).
- Telegram credentials sunt în plist, nu în script — mai sigur (nu apar în `ps aux`).
