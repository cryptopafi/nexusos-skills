# ESCALATION-SENTINEL
**Version**: 1.0.0
**Status**: ACTIVE
**Domain**: Infrastructure / Monitoring
**Owner**: Genie (MacM4)
**Last Updated**: 2026-03-13

---

## Purpose

Procedura de escaladare automată când SENTINEL este offline mai mult de 30 de minute. Genie detectează absența unui update recent în `SENTINEL-HEALTH.md`, încearcă restart, și dacă acesta eșuează, alertează Pafi pe Telegram. Dacă Pafi nu răspunde în 10 minute, se activează un checklist manual de fallback.

---

## Trigger Conditions

- `SENTINEL-HEALTH.md` nu a fost actualizat în ultimele **30 de minute**
- Genie detectează absența semnalului heartbeat SENTINEL
- Apel explicit: `escalation-sentinel` din orice context Genie

---

## Prerequisites

- `SENTINEL-HEALTH.md` path cunoscut (implicit: `~/.nexus/monitoring/SENTINEL-HEALTH.md`)
- Telegram bot activ: `@claudemacm4_bot` (Lis / MacM4)
- SENTINEL service name/plist cunoscut (implicit: `com.sentinel.monitor`)
- Acces la `launchctl` pe MacM4

---

## Phase 1 — Detection (T+0)

### Step 1.1 — Verifică timestamp SENTINEL-HEALTH.md

```bash
HEALTH_FILE="$HOME/.nexus/monitoring/SENTINEL-HEALTH.md"
THRESHOLD_MINUTES=30

if [ ! -f "$HEALTH_FILE" ]; then
  echo "SENTINEL-HEALTH.md lipsește complet — SENTINEL posibil niciodată pornit"
  SENTINEL_STATUS="MISSING"
else
  LAST_MODIFIED=$(stat -f "%m" "$HEALTH_FILE" 2>/dev/null || stat -c "%Y" "$HEALTH_FILE")
  NOW=$(date +%s)
  AGE_MINUTES=$(( (NOW - LAST_MODIFIED) / 60 ))

  if [ "$AGE_MINUTES" -ge "$THRESHOLD_MINUTES" ]; then
    echo "SENTINEL offline de $AGE_MINUTES minute(e) — ESCALADARE ACTIVATĂ"
    SENTINEL_STATUS="OFFLINE"
  else
    echo "SENTINEL OK — ultima actualizare acum $AGE_MINUTES minute(e)"
    SENTINEL_STATUS="OK"
    exit 0
  fi
fi
```

### Step 1.2 — Log evenimentul

Scrie în `~/.nexus/logs/escalation-sentinel.log`:

```
[TIMESTAMP] ESCALATION-SENTINEL TRIGGERED
Status: OFFLINE / MISSING
Age: X minutes
Health file: ~/.nexus/monitoring/SENTINEL-HEALTH.md
```

---

## Phase 2 — Restart Attempt (T+1 min)

### Step 2.1 — Încearcă restart SENTINEL via launchctl

```bash
PLIST_NAME="com.sentinel.monitor"

echo "[$(date)] Attempting SENTINEL restart..."

# Stop
launchctl unload ~/Library/LaunchAgents/${PLIST_NAME}.plist 2>/dev/null
sleep 2

# Start
launchctl load ~/Library/LaunchAgents/${PLIST_NAME}.plist 2>/dev/null
sleep 5
```

### Step 2.2 — Verifică dacă restart-ul a reușit

Așteaptă 2 minute, apoi re-verifică `SENTINEL-HEALTH.md`:

```bash
sleep 120

NEW_MODIFIED=$(stat -f "%m" "$HEALTH_FILE" 2>/dev/null || stat -c "%Y" "$HEALTH_FILE")
if [ "$NEW_MODIFIED" -gt "$LAST_MODIFIED" ]; then
  echo "SENTINEL restart REUȘIT — health file actualizat"
  RESTART_STATUS="SUCCESS"
  # Notifică Pafi că SENTINEL a fost repornit cu succes
  # → Trimite mesaj Telegram informativ (non-urgent)
else
  echo "SENTINEL restart EȘUAT — escaladare la Pafi"
  RESTART_STATUS="FAILED"
fi
```

**Dacă restart reușit** → trimite notificare informativă pe Telegram și **STOP procedură**.

**Dacă restart eșuat** → continuă cu Phase 3.

---

## Phase 3 — Alertă Pafi pe Telegram (T+3 min)

### Step 3.1 — Trimite alertă urgentă

Mesaj Telegram via `@claudemacm4_bot` (Lis):

```
🚨 ESCALATION-SENTINEL

SENTINEL este OFFLINE de [X] minute.
Restart automat: EȘUAT.

Acțiune necesară:
1. Verifică MacM4 → procesul SENTINEL
2. Răspunde DA dacă preiei manual
3. Răspunde NU dacă vrei fallback automat

⏱ Aștept răspunsul tău 10 minute.
[T+3 min — 2026-03-13 HH:MM]
```

### Step 3.2 — Setează timer 10 minute

```bash
ALERT_TIME=$(date +%s)
RESPONSE_DEADLINE=$((ALERT_TIME + 600))  # 10 minute
echo "Aștept răspuns Pafi până la $(date -d @$RESPONSE_DEADLINE)"
```

### Step 3.3 — Monitorizare răspuns

Genie verifică la fiecare 60 secunde dacă:
- Pafi a răspuns pe Telegram (DA / NU / orice mesaj)
- SENTINEL-HEALTH.md a fost actualizat (auto-recovery)

**Dacă Pafi răspunde** → confirmă și transferă control manual → **STOP procedură automată**.

**Dacă nu răspunde în 10 min** → continuă cu Phase 4.

---

## Phase 4 — Fallback Manual Checklist (T+13 min)

### Step 4.1 — Trimite checklist complet pe Telegram

```
⚠️ FALLBACK MANUAL — SENTINEL

Pafi nu a răspuns. Activez checklist manual:

CHECKLIST SENTINEL RECOVERY:

□ 1. Deschide Terminal pe MacM4
□ 2. Rulează: launchctl list | grep sentinel
□ 3. Dacă nu apare: launchctl load ~/Library/LaunchAgents/com.sentinel.monitor.plist
□ 4. Verifică logs: tail -50 ~/.nexus/logs/sentinel.log
□ 5. Dacă eroare Python/Node: reinstalează dependențele
□ 6. Verifică spațiu disk: df -h ~
□ 7. Verifică RAM: vm_stat | head -5
□ 8. Repornește MacM4 dacă nimic nu funcționează

📁 Health file: ~/.nexus/monitoring/SENTINEL-HEALTH.md
📋 Logs: ~/.nexus/logs/sentinel.log
🔧 Plist: ~/Library/LaunchAgents/com.sentinel.monitor.plist

Raportează status după rezolvare.
```

### Step 4.2 — Activează monitoring degradat

Genie intră în mod degradat: verifică manual la fiecare 15 minute dacă SENTINEL-HEALTH.md a fost actualizat, fără a mai trimite alerte suplimentare (anti-spam).

### Step 4.3 — Log final

```
[TIMESTAMP] ESCALATION-SENTINEL — FALLBACK ACTIVAT
Restart automat: EȘUAT
Răspuns Pafi: ABSENT (>10 min)
Checklist trimis pe Telegram
Monitoring degradat: ACTIV (15 min interval)
```

---

## Recovery Confirmation

Când SENTINEL-HEALTH.md este actualizat din nou (indiferent de cine a rezolvat):

1. Genie detectează recovery
2. Trimite notificare Telegram: `✅ SENTINEL ONLINE — recovery confirmat`
3. Resetează intervalul de monitoring la normal (30 min threshold)
4. Scrie în log: `ESCALATION-SENTINEL RESOLVED at [TIMESTAMP]`

---

## Escalation Timeline Summary

| Timp | Acțiune |
|------|---------|
| T+0 | SENTINEL detectat offline (>30 min) |
| T+1 | Log + restart automat încercat |
| T+3 | Verificare restart + alertă Pafi pe Telegram (dacă restart eșuat) |
| T+13 | Fallback checklist manual trimis (dacă Pafi nu răspunde) |
| T+13+ | Monitoring degradat la 15 min interval |
| Recovery | Notificare confirmare + reset normal |

---

## Notes

- **Anti-spam**: O singură alertă urgentă per incident. Checklist-ul se trimite o singură dată.
- **Auto-recovery detection**: Dacă SENTINEL revine online singur în orice moment, procedura se oprește automat.
- **Plist name**: Implicit `com.sentinel.monitor` — ajustează dacă e diferit în sistem.
- **Telegram bot**: Folosește `@claudemacm4_bot` (Lis, MacM4) ca relay pentru toate mesajele.
- **Log location**: `~/.nexus/logs/escalation-sentinel.log` — verifică după fiecare incident.

---

## Related Procedures

- `SENTINEL-HEALTH` — procedura principală de monitorizare
- `HEARTBEAT` — heartbeat general Genie
- `TRAVEL-AGENT` — exemplu procedură cu faze similare

---

*Procedură creată: 2026-03-13 | FORGE'd by Genie*
