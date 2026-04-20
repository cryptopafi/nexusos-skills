---
name: audit-pro-self-audit-procedure
description: Use when audit-pro needs full-triangle self-audit via Opus + GPT-5-codex + Gemini to fix drift
---

# Problema
Audit-pro v1.1.0 avea drift între sursele de adevăr. Un self-audit FULL_TRIANGLE (Opus + GPT-5-codex + Gemini-2.5-pro) a descoperit 3 HIGH correctness/safety bugs în loop controller-ul propriu: (H1) SKILL.md Concurrent Access Guard documenta lock la ~/.claude/locks/audit-pro.lock dar scripts/ralph-audit-loop.sh folosea /tmp/audit-pro/<hash>.lock + exit 0 silent pe contention; (H2) category enum drift în 5 locuri: SKILL.md canonical protocol|fitness|compat|lobster vs codex-audit-dispatch.sh prompt/schema logic|structure|compliance|resilience|integration|portability vs gemini-audit-dispatch.sh prompt fără lobster → Step 8 merge dedup by category eșuează; (H3) sed -e 's/^iteration: .*/.../' în state file update este line-anchored dar nu frontmatter-scoped → corupe prompt body dacă conține linii care încep cu iteration: sau previous_score:.

# Procedura
1. H1 ralph-audit-loop.sh: schimbă `LOCK_DIR="${AUDIT_PRO_LOCK_DIR:-/tmp/audit-pro}"` în `${HOME}/.claude/locks/audit-pro`. Inițializează `TARGET_HASH=""` la top-level (fix set -u crash in trap). Înlocuiește `echo ⚠️ Skipping >&2; exit 0` cu `echo "ERROR: Another audit is running (PID $lock_pid). Wait or ..." >&2; exit 1`.
2. H1 SKILL.md: rescrie secțiunea Concurrent Access Guard pentru a descrie scheme per-target cu LOCK_DIR user-scoped și <target_hash>.lock format, match cu runtime-ul ralph.
3. H2 canonical enum = SKILL.md's 7: security, logic, naming, protocol, fitness, compat, lobster. Update 5 drift points: codex-audit-dispatch.sh L176 (category rule) + L196 (anti-pattern list) + codex-audit-schema.json L44 (enum) + gemini-audit-dispatch.sh L132 (JSON example category union).
4. H3 ralph-audit-loop.sh: înlocuiește `sed -e 's/^iteration:.../s/^previous_score:.../'` cu awk care numără `^---$` și aplică rewrite DOAR când `fm_count == 1` (înainte de al doilea `---`).
5. Syntax-check: `bash -n` pe toate shell scripts. `python3 -c "import json; json.load(open(...))"` pe schema JSON.
6. Smoke-test awk cu state file care conține `iteration:` în prompt body → verifică că doar frontmatter line e modificată.

# Enforcement Loop
Verifică: `grep -n 'LOCK_DIR.*HOME/.claude/locks/audit-pro' ~/.nexus/audit/scripts/ralph-audit-loop.sh` → line match. `grep -n 'exit 1' ~/.nexus/audit/scripts/ralph-audit-loop.sh` → match în acquire_lock. `grep 'lobster' ~/.nexus/audit/scripts/codex-audit-dispatch.sh ~/.nexus/audit/scripts/codex-audit-schema.json ~/.nexus/audit/scripts/gemini-audit-dispatch.sh` → toate 3 fișiere match. `grep 'awk -v iter' ~/.nexus/audit/scripts/ralph-audit-loop.sh` → match. Smoke test: creează state file test cu iteration: body line, rulează awk, verifică body intact. Dacă vreunul missing → HIGH severity regression.
