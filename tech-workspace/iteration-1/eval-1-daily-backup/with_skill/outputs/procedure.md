# NEXUS-DAILY-BACKUP — Procedură Standard de Operare

**Status**: ACTIVE
**Creat**: 2026-03-13
**Versiune**: 1.0
**Regulă asociată**: OPS-H-003 (Data Integrity — Backup Obligatoriu pentru State Critic)
**Scope**: Backup zilnic automat al memoriei NexusOS (`~/.nexus/memory/` și `~/.claude/projects/`) pe VPS, cu alertă Telegram la eșec.

---

## 1. Problema

Memoria NexusOS și proiectele Claude reprezintă starea operațională critică a întregului sistem Genie + agent stack. Fără un backup regulat, orice incident local (corupție disk, ștergere accidentală, eroare de sync, defecțiune hardware pe MacM4) poate duce la pierderea irecuperabilă a contextului acumulat, procedurilor, task-urilor active și configurațiilor agenților.

Situații acoperite de această procedură:
- Backup zilnic automatizat la 03:00 (ora minimă de activitate, risc zero de conflict cu procese active)
- Verificarea integrității transferului (exit code + validare dimensiune arhivă)
- Notificare imediată pe Telegram dacă backup-ul eșuează, indiferent de cauză (network timeout, SSH failure, spațiu insuficient pe VPS, eroare rsync/tar)
- Rotație arhive pentru a evita saturarea spațiului pe VPS (păstrare ultimele N zile)

---

## 2. Procedura

### Pas 1: Verificare Prerequisite
Înainte de prima rulare (și la fiecare modificare), verifică:
- SSH key-based auth configurat între MacM4 și VPS `89.116.229.189` (user `pafi`, fără parolă interactivă)
- `rsync` disponibil pe MacM4 (`/opt/homebrew/bin/rsync` sau `/usr/bin/rsync`)
- Token Telegram bot (`@claudemacm4_bot`) și `CHAT_ID` disponibile în environment sau fișier `.env` securizat (nu hardcodate în script)
- Director destinație pe VPS creat: `/home/pafi/backups/nexus-memory/`

### Pas 2: Creare Script de Backup
Scriptul (`~/.nexus/scripts/daily-backup.sh`) realizează în ordine:
1. Setează variabile: timestamp (format `YYYY-MM-DD`), paths sursă, path destinație VPS, fișier log local (`~/.nexus/logs/backup.log`)
2. Rulează `rsync -avz --delete` cu SSH pentru `~/.nexus/memory/` → VPS
3. Rulează `rsync -avz --delete` cu SSH pentru `~/.claude/projects/` → VPS
4. Verifică exit code-ul fiecărui `rsync` — dacă oricare ≠ 0, marchează backup ca FAILED
5. Dacă FAILED: trimite alert Telegram via `curl` cu mesaj clar (timestamp + cauza din stderr)
6. Dacă SUCCESS: loghează succesul local cu timestamp și dimensiunea totală transferată
7. Rotație: șterge de pe VPS arhivele mai vechi de 30 de zile (dacă se folosește arhivare tar în loc de sync live)

### Pas 3: Configurare LaunchAgent (cron macOS)
Creează `~/Library/LaunchAgents/com.nexus.daily-backup.plist` cu:
- `StartCalendarInterval`: ora 03, minutul 00
- `ProgramArguments`: calea absolută la `daily-backup.sh` (`/bin/bash /Users/pafi/.nexus/scripts/daily-backup.sh`)
- `StandardOutPath` și `StandardErrorPath`: fișiere log separate (`~/.nexus/logs/backup-stdout.log`, `~/.nexus/logs/backup-stderr.log`)
- `EnvironmentVariables`: include `PATH` complet (include `/opt/homebrew/bin`) și variabilele Telegram (`BOT_TOKEN`, `CHAT_ID`)

Încarcare agent: `launchctl load ~/Library/LaunchAgents/com.nexus.daily-backup.plist`

### Pas 4: Alertă Telegram la Eșec
Formatul mesajului de alertă trebuie să conțină:
- Identificator clar: `[NEXUS BACKUP FAILED]`
- Timestamp UTC al tentativei
- Care dintre cele două surse a eșuat (`memory` / `projects` / `ambele`)
- Codul de eroare rsync sau mesajul din stderr (primele 200 caractere)
- Instrucțiune de acțiune: `Verifică VPS + SSH pe MacM4`

### Pas 5: Test Manual Post-Setup
Rulează manual o dată pentru a valida întregul flux:
```
bash ~/.nexus/scripts/daily-backup.sh
```
Verifică:
- Fișierele au ajuns pe VPS (`ssh pafi@89.116.229.189 ls /home/pafi/backups/nexus-memory/`)
- Log local conține timestamp și dimensiuni
- Dacă simulezi eșec (ex: oprești SSH temporar), Telegram primește alertă

### Test Cases
1. **Normal flow**: MacM4 online, VPS accesibil, SSH funcțional → ambele directoare sincronizate pe VPS, log local actualizat cu SUCCESS + dimensiune
2. **Edge case — VPS unreachable**: `rsync` timeout după 30s → script marchează FAILED, trimite Telegram alert cu `Connection timed out`, scriptul nu blochează (timeout explicit în SSH args)
3. **Failure case — SSH key lipsă**: `rsync` returnează exit code 255 → alert Telegram cu `Permission denied (publickey)`, nu se retentativă automată (operatorul trebuie să intervină manual)

---

## 3. Cortex Logging

La fiecare execuție cu succes a procedurii de CREARE/MODIFICARE a acestui backup setup, se salvează în Cortex:

```json
{
  "text": "NEXUS-DAILY-BACKUP | backup zilnic 03:00 ~/.nexus/memory/ + ~/.claude/projects/ → VPS 89.116.229.189 | Telegram alert la eșec | LaunchAgent configurat",
  "collection": "procedures",
  "metadata": {
    "type": "procedure",
    "procedure": "NEXUS-DAILY-BACKUP",
    "rule_id": "OPS-H-003",
    "has_enforcement_loop": true,
    "forge_version": "1.4",
    "tags": ["backup", "nexus", "infra", "vps", "telegram", "launchagent", "procedure"]
  }
}
```

La fiecare rulare a script-ului de backup în sine, se loghează local în `~/.nexus/logs/backup.log` (nu în Cortex — volum prea mare pentru daily entries).

---

## 4. Enforcement Loop (META-H-002)

### WHERE
- **LaunchAgent macOS** — `com.nexus.daily-backup.plist` declanșează automat la 03:00
- **NexusOS Health Daemon** — `test-all-procedures.js` verifică existența plist-ului și a scriptului la startup
- **Session Checklist** — Genie verifică la deschiderea sesiunii de dimineață dacă backup-ul de azi a rulat (via log)

### WHEN
- **Automat**: zilnic la 03:00 (LaunchAgent)
- **Manual**: la orice modificare a structurii `~/.nexus/memory/` sau `~/.claude/projects/` (Pafi poate rula `daily-backup.sh` manual oricând)
- **Trigger de urgență**: după orice incident de corupție detectat de sync-memory.sh

### HOW (violation detection)
- Log check: dacă `~/.nexus/logs/backup.log` nu conține un entry de azi cu `SUCCESS` la 07:00 → morning-ingest.sh emite warning în brief-ul de dimineață
- Telegram alert: absența alertei NU înseamnă că backup-ul a rulat — verificarea pozitivă este în log
- VPS check: `ssh pafi@89.116.229.189 ls -lt /home/pafi/backups/nexus-memory/ | head -5` — primul entry trebuie să fie de azi
- Runner: `~/.nexus/scripts/check-backup-health.sh` (rulat de morning-ingest.sh la 07:00)

### CONNECT
- **OPS-H-003** (Data Integrity) → această procedură este implementarea operațională a regulii
- **sync-memory.sh** (`~/.claude/sync-memory.sh`) → complementar (sync Git la 1 min), backup-ul VPS este layer suplimentar offline
- **morning-ingest.sh** (`~/.nexus/scripts/morning-ingest.sh`) → apelează `check-backup-health.sh` și include rezultatul în brief-ul de dimineață
- **`procedure-health.json`** → adaugă entry: `{"id": "NEXUS-DAILY-BACKUP", "status": "ACTIVE", "last_verified": "2026-03-13", "enforcement": "launchagent+log-check"}`
- **`@claudemacm4_bot`** → canal Telegram pentru alertele de eșec (același bot folosit de Lis PA)

### VERIFY (procedural checkpoint)
La finalul configurării inițiale sau după orice modificare a procedurii, agentul verifică:
- [ ] Procedura a fost executată complet? (toți pașii §2 bifați: script creat, LaunchAgent creat și încărcat, test manual rulat)
- [ ] Output-ul satisface criteriile din §1? (backup rulat cu succes pe VPS, alert Telegram funcțional când se simulează eșec)
- [ ] VK emis în sesiune? (ambele linii vizibile pentru Pafi)
- [ ] Dacă oricare = NU → procedura NU e completă, nu marca DONE

### MODEL ROUTING
| Activitate | Model | Motivul |
|-----------|-------|---------|
| Creare procedură + script inițial | Sonnet 4.6 (Genie) | Task standard, template FORGE |
| Debugging SSH / rsync errors | Sonnet 4.6 (Genie direct) | Diagnostic simplu, nu necesită reasoning profund |
| Audit periodic al procedurii | Opus 4.6 subagent | Review structural + validare securitate SSH keys |
| Scrierea scriptului bash complet | Codex (GPT-5) | Cod > 10 linii → Codex, nu Genie |

---

## 5. Dependențe

| Componentă | Rol | Path/Endpoint |
|-----------|-----|---------------|
| `daily-backup.sh` | Script principal backup | `~/.nexus/scripts/daily-backup.sh` |
| `com.nexus.daily-backup.plist` | LaunchAgent macOS (scheduler 03:00) | `~/Library/LaunchAgents/com.nexus.daily-backup.plist` |
| `check-backup-health.sh` | Verificare log dimineață | `~/.nexus/scripts/check-backup-health.sh` |
| VPS backup dir | Destinație remote | `pafi@89.116.229.189:/home/pafi/backups/nexus-memory/` |
| `@claudemacm4_bot` | Telegram alert channel | Token în `.env` securizat, `CHAT_ID` = Pafi personal |
| `backup.log` | Log local execuții | `~/.nexus/logs/backup.log` |
| `sync-memory.sh` | Sync Git complementar (1 min) | `~/.claude/sync-memory.sh` |

---

## 6. Metrics

| Metrică | Ce măsoară | Target |
|---------|-----------|--------|
| Backup success rate | % zile cu backup SUCCESS din ultimele 30 | ≥ 98% (max 1 eșec/lună) |
| Transfer size | MB transferate per backup (delta rsync) | < 50 MB/zi în condiții normale |
| Backup duration | Timp total execuție script | < 5 minute |
| Alert latency | Timp de la eșec până la Telegram alert | < 60 secunde |
| VPS retention | Număr de zile de backup disponibile pe VPS | 30 zile rolling |

---

## Checklist Pre-Publicare

- [x] Regulă asociată există: OPS-H-003 (Data Integrity)
- [x] Enforcement loop complet: WHERE + WHEN + HOW + CONNECT + VERIFY
- [x] VERIFY checkpoint prezent cu cele 3 checks obligatorii
- [x] Procesul din WHERE referențiază această procedură (morning-ingest.sh + health daemon)
- [x] Entry documentat pentru `procedure-health.json`
- [x] Salvat în Cortex cu metadata: `rule_id`, `type: procedure`, `has_enforcement_loop: true`, `forge_version: "1.4"`
- [x] Descrie CE nu CUM (zero cod inline >10 linii — scriptul bash complet merge la Codex)
- [x] VK format specificat (per VK-H-001)
- [x] Test cases documentate — 3 cazuri (normal + edge + failure)

---

✅ [PROC] FORGE | §1✓ §2✓ §3✓ §4✓ VER✓ | complete

✅ [CORTEX] "NEXUS-DAILY-BACKUP" | FORGE ✓ | rule: OPS-H-003 | v1.0
