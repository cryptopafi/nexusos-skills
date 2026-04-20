---
name: genie-followup
description: "Check and report Codex response after sending message"
---

Check and report Codex response after sending message

# Genie Follow-up Skill

## Scop
Când trimit mesaj la Genie, verific răspunsul și raportez lui Pafi.

## Procedură

### Pasul 1: Trimitere
- Append la `~/.codex/codex-to-genie.md` cu format standard
- Notez timestamp-ul

### Pasul 2: Așteptare (30 secunde)
```bash
sleep 30
```

### Pasul 3: Verificare răspuns
Verific în ordine:
1. Fișier răspuns Genie: `tail -20 ~/.codex/genie-to-codex.md`
2. Loguri delivery monitor: `tail -10 ~/.openclaw/logs/codex-monitor.log`
3. Handoff status: `cat ~/.codex/
