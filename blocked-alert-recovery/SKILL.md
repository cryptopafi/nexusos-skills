---
name: blocked-alert-recovery
description: Use when receiving X BLOCKED alert — rapid triage runbook to identify cause and resume execution
---

# BLOCKED Alert Recovery — Procedură Standard de Operare

**Status**: ACTIVE
**Creat**: 2026-02-28
**Versiune**: 1.0
**Regulă asociată**: OPS-H-001
**Scope**: Recovery rapid când primești 🔴 X BLOCKED pe @Claudeautomationbot — forward în @Claudemacm4_bot și Genie ghidează pașii.

---

## 1. Problema

Sistemul (system-watchdog, nexus-optimizer, codex-watchdog) detectează că un component critic nu răspunde și trimite alertă 🔴 X BLOCKED pe @Claudeautomationbot.

Situații acoperite:
- 🔴 Tailscale BLOCKED — VPN inaccesibil, 100.81.233.9 unreachable
- 🔴 Cortex BLOCKED — API la :6400 nu răspunde
- 🔴 Mission Control BLOCKED — UI la :3200 nu răspunde
- 🔴 VPS SSH BLOCKED — SSH la 89.116.229.189 eșuat
- 🔴 Codex BLOCKED — daemon stuck sau pending fără execuție

---

## 2. Procedura

### Pas 1: Forward mesajul
Forwardează mesajul 🔴 BLOCKED din @Claudeautomationbot în @Claudemacm4_bot. Genie detectează automat tipul și oferă pașii specifici.

### Pas 2: Recovery per component

**Tailscale BLOCKED**
(1) Deschide Tailscale app → Connect
(2) Dacă nu merge: System Settings → VPN → Tailscale → Connect
(3) Verificare: ping 100.81.233.9

**Cortex BLOCKED**
(1) ssh pafi@89.116.229.189
(2) cd ~/repos/cortex && docker compose up -d
(3) Verificare: curl http://localhost:6400/api/health

**Mission Control BLOCKED**
(1) ssh pafi@89.116.229.189
(2) pm2 restart mission-control
(3) Verificare: curl http://100.81.233.9:3200

**VPS SSH BLOCKED**
(1) Verifică Hetzner dashboard — server status
(2) Dacă DOWN: Power cycle din dashboard
(3) Dacă UP dar SSH fail: verifică firewall rules în Hetzner

**Codex BLOCKED**
(1) launchctl kickstart -k gui/$(id -u)/com.genie.codex-daemon
(2) Așteaptă 90s, verifică ~/.codex/codex-to-genie.md
(3) Dacă persistent: cat ~/.openclaw/logs/codex-daemon.log | tail -20

### Pas 3: Confirmare
După recovery, Genie verifică automat la următorul ciclu watchdog (5 min) că alerta a dispărut.

---

## 3. Cortex Logging

După recovery confirmat, Genie stochează:

{
  "text": "RECOVERY: [component] BLOCKED resolved. Cauza: [descriere]. Fix: [pași urmați].",
  "collection": "sessions",
  "metadata": {
    "type": "incident_recovery",
    "procedure": "BLOCKED-ALERT-RECOVERY",
    "rule_id": "OPS-H-001",
    "tags": ["recovery", "blocked", "watchdog"]
  }
}

---

## 4. Enforcement Loop (META-H-002)

### WHERE
La primirea oricărui mesaj 🔴 BLOCKED forwardat în @Claudemacm4_bot — Genie detectează via getCortexProcedures și aplică pașii.

### WHEN
La fiecare incident BLOCKED — fără excepții. Cooldown watchdog = 30 min (nu spam).

### HOW (violation detection)
- Alert BLOCKED primit dar fără recovery în 30 min → follow-up automat de la watchdog
- Recovery nereportat în Cortex sessions → procedura incompleta
- Runner: system-watchdog.sh (ogni 5 min), codex-watchdog.sh

### CONNECT
- OPS-H-001 → operații critice necesită procedură documentată
- system-watchdog.sh → trimite alertele 🔴
- codex-watchdog.sh → trimite 🔴 Codex BLOCKED
- @Claudemacm4_bot relay → getCortexProcedures găsește această procedură automat

### VERIFY
- [ ] Componenta răspunde după recovery?
- [ ] Watchdog confirmă absența alertei la următorul ciclu?
- [ ] Incident logat în Cortex sessions?
