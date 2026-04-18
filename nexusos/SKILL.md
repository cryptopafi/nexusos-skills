---
name: nexusos
description: "Control NexusOS multiagentic system — status, task dispatch, logs, heartbeat trigger. Use when the user says '/nexusos', 'nexusos status', 'dispatch task', 'nexusos logs', or wants to interact with the NexusOS multi-agent orchestration system."
argument-hint: [status|dispatch|logs|kick|smoke|tasks|agents] [args...]
user_invocable: true
---

# /nexusos — NexusOS Multiagentic Control

Interface unificată pentru sistemul NexusOS multiagentic de pe MacM4.

## Arguments

```
/nexusos                          — status complet sistem (default)
/nexusos status                   — status: toți agenții + active tasks
/nexusos dispatch <desc> [agent]  — GENIE V2 routing pipeline: classify, budget, confirm, dispatch
/nexusos logs [agent] [N]         — ultimele N linii de log (default 20)
/nexusos kick                     — trigger manual GENIE heartbeat
/nexusos smoke                    — rulează nexus-smoke-test.sh
/nexusos tasks                    — listează task-urile active + completed
/nexusos agents                   — listează toți agenții cu status + capabilities
```

## Execution

### Parse arguments

Primul argument determină comanda. Dacă nu există argument → defaultează la `status`.

---

### CMD: status (default)

Rulează în paralel:

```bash
cat ~/.nexus/workspace/intel/GENIE-STATUS.md
cat ~/.nexus/workspace/intel/SENTINEL-HEALTH.md
ls ~/.nexus/workspace/active/ 2>/dev/null
ls ~/.nexus/workspace/completed/ 2>/dev/null | wc -l
```

Afișează raport structurat cu TOȚI agenții din agent-registry.yaml:

```
NexusOS Status — {timestamp}

GENIE:     {status din GENIE-STATUS.md — Cycle N, GREEN/YELLOW/RED}
TECH:      {status} [sub: builder, fixer, integrator, pipeliner, product]
DELPHI:    {status}
MERCURY:   {status} [sub: seo, content, ads, smsads, outreach]
ECHELON:   {status} [sub: collector, enricher, scout, synthesizer, dispatcher]
SENTINEL:  {status} [sub: collector, triage, responder]
CONCIERGE: {status}
HEALTH:    {status}
TRAVEL:    {status}
AUCTION:   {status}

Active tasks:    {N} — {lista task IDs sau "none"}
Completed tasks: {N}
Alerts: {alerts din SENTINEL-HEALTH.md sau "none"}
```

---

### CMD: dispatch

**Usage**: `/nexusos dispatch <descriere task> [agent]`

**GENIE V2 Routing Pipeline — urmează pașii în ordine:**

#### PASUL 1: Routing Classification

**Dacă agent e specificat explicit** → sari la Pasul 2 cu agentul dat (confidence 1.0).

**Dacă agent nu e specificat**, clasifică prin precedence:

**1a. Block keywords** — dacă descrierea ÎNCEPE cu unul din:
- `/tech` → tech | `/delphi` sau `/delphi-pro` sau `/iris` → delphi | `/mercury` → mercury
- `/sentinel` → sentinel | `/travel` → travel | `/health` → health
- `/auction` → auction | `/echelon` → echelon | `/pafi` → concierge | `/genie` → genie
→ Route direct, confidence 1.0.

**1b. Agent keywords** — caută cuvinte cheie în descriere (source of truth: routing-table.yaml):
- `delphi`: research, investigate, literature, evidence, deep-dive, deep dive, studii, cercetare
- `mercury`: campaign, content, outreach, seo, newsletter, marketing, social media, smsads, affiliate, ad copy, lead gen, keyword research
- `tech`: code, implement, fix, build, deploy, refactor, script, configure, pipeline, implementare, launchagent, daemon, cron, ci-cd, wire, connect, integrate, mcp, website, mobile app, desktop app, saas
- `sentinel`: monitor, alert, watchdog, restart, stale, offline
- `echelon`: intelligence, intel signal, trend detection, pattern analysis, synthesis report, daily brief
- `travel`: flight, hotel, flights, booking, visa, itinerary, zbor, cazare
- `health`: supplement, blood panel, vitals, workout, blood test, health protocol
- `concierge`: email, calendar, meeting, expense, budget, reminder, triage
- `auction`: auction, bid, lot, troostwijk, bva, surplex, catawiki, licitatie
→ Primul match câștigă.

**1c. Domain classification** — dacă niciun agent keyword nu s-a potrivit, check classification_rules (mai broad):
- `development`: security audit, audit, code review, test, refactor, script, fix, bug, deploy, pipeline
- `research`: analiza, insight, raport, cauta, studiaza, investigate, arxiv, what is, explain, define
- `marketing`: campanie, post, copy, social media, lead, funnel, outreach, newsletter
- `intelligence`: signal, source, trend, synthesis, intel, pattern detection, channel monitor
- `ops`: sync, monitoring, backup, cron, disk, restart
- `travel`: destination, cazare, zbor
- `health`: exercise, longevity, meditation
- `personal` → concierge: habit, contact, followup, schedule
- `auction`: industrial equipment, bidding
→ Map domain to agent: research→delphi, marketing→mercury, development→tech, ops→sentinel, intelligence→echelon, personal→concierge.

**1d. Fallback** — dacă niciun match → spune utilizatorului să specifice agentul explicit.

#### PASUL 2: Estimare Complexitate

- Cuvinte cheie `audit, architecture, strategy, full, complete, deep, comprehensive` → **HIGH**
- Cuvinte cheie `research, analyze, investigate, compare, review` → **MEDIUM**
- Altfel → **LOW**

Budget estimat: LOW=USD0.50 | MEDIUM=USD2.00 | HIGH=USD5.00

#### PASUL 3: Check Agent Status

Citește `~/.nexus/v2/config/agent-registry.yaml`.

- `status: active` → proceed
- `status: degraded` sau `offline` → folosește fallback agent din routing-table.yaml (de obicei `genie`)
- `status: planned`, `deferred`, sau `building` → avertizează userul, sugerează alternativă
- `status: deployed` → tratează ca active (ex: auction)
- Agent necunoscut (nu există în registry) → abort dispatch, sugerează `/nexusos agents`

#### PASUL 4: Prezintă Routing Decision

```
NexusOS Dispatch Decision:
Task: {descriere}
Agent: {agent} ({domain/role})
Complexity: {LOW/MEDIUM/HIGH}
Est. budget: ${budget}
Timeout: {timeout_s}s

Proceed? (yes/no)
```

HIGH complexity ($5.00) → OBLIGATORIU confirmare Pafi (IL-3).

#### PASUL 5: La confirmare YES — creare workspace + dispatch

**5a. Generează task_id**: `nx-{YYYYMMDD}-{4 random chars alfanumerici}`

**5b. Scrie descrierea în fișier temp** (previne shell injection din ghilimele/newline-uri):
```bash
printf '%s' "{descriere completă cu context expandat}" > /tmp/nx-desc-{task_id}.txt
```

**5c. Rulează nexus-task-create.sh**:
```bash
~/.nexus/scripts/nexus-task-create.sh "{task_id}" "@/tmp/nx-desc-{task_id}.txt" "{agent}" "{complexity}" "{budget}" "{timeout_s}"
```
Dacă scriptul nu este disponibil, folosește procedura manuală din **Appendix A**.

**5d. Write acceptance_criteria sidecar** (if acceptance_criteria specified):
When acceptance_criteria are specified in the dispatch, also write `acceptance_criteria.yaml` sidecar file in the task workspace directory using the template from `~/.nexus/v2/lib/templates/ACCEPTANCE-CRITERIA-TEMPLATE.yaml`. This sidecar is read by `verify-acceptance.sh` with priority over DISPATCH.md inline criteria.

Note: fswatch daemon auto-logs DISPATCHED→CLAIMED→STARTED. GENIE only logs NEW→DISPATCHED (handled by script).

#### PASUL 6: Execute via Agent

**Special routing — verifică MAI ÎNTÂI dacă task-ul conține:**
- `audit` → `Agent(subagent_type="forge-auditor")`
- `fix finding` sau `safe fix` → `Agent(subagent_type="safe-fixer")`
- `code review` → `Agent(subagent_type="code-reviewer")`
- `check health` sau `system health` → `Agent(subagent_type="incident-responder")`
- `intel summary` sau `daily brief` → `Agent(subagent_type="intel-synthesizer")`
- `triage signals` → `Agent(subagent_type="signal-triage")`
- `research synthesis` sau `INSIGHT` → `Agent(subagent_type="research-synthesizer")`
- `search cortex` → `Agent(subagent_type="cortex-searcher")`
- `ops` + (`install` sau `configure` sau `deploy` sau `setup`) → `Agent(subagent_type="ops-executor")`

**Generic dispatch dacă niciun special match:**

Citește (dacă există):
- `~/.nexus/v2/agents/{agent}/SKILL.md`
- `~/.nexus/v2/agents/{agent}/iron-laws.md`

Construiește prompt:
```
You are {AGENT_NAME} from NexusOS v2.0.

## Your Capabilities
{conținut SKILL.md}

## Your Constraints (Iron Laws)
{conținut iron-laws.md}

## Task
{conținut body din DISPATCH.md}

## Output
Write your results to: ~/.nexus/workspace/active/{task_id}/output.md
Update PROGRESS.md status to EXECUTING when you start, REVIEWING when done.
```

Mod execuție:
- TECH tasks → `Agent(mode="bypassPermissions")`
- Toți ceilalți → `Agent(mode="auto")`

#### PASUL 7: Judge (MEDIUM sau HIGH)

- **LOW**: auto-PASS, skip judge.
- **MEDIUM**: verificare rapidă (Sonnet) — output.md există și adresează task-ul?
- **HIGH**: quality score detaliat (Sonnet) — completitudine, corectitudine, actionability (0-100).
  - Score < 70: o singură tentativă de revizie, apoi raportează indiferent.

**JUDGE.md artifact** (MANDATORY pentru MEDIUM și HIGH):

După judging, scrie JUDGE.md folosind Write tool (nu heredoc). Conținut:
```yaml
---
task_id: {task_id}
judge_model: sonnet-4-6
judge_timestamp: {ISO timestamp}
complexity: {MEDIUM/HIGH}
verdict: PASS  # sau FAIL
score: null  # null pentru MEDIUM, 0-100 pentru HIGH
---

{2-3 propoziții de evaluare: ce a livrat agentul, ce lipsește dacă e cazul, verdict final.}
```

**Path cu fallback** (task may move to completed/ before GENIE writes):
1. Încearcă `~/.nexus/workspace/active/{task_id}/JUDGE.md`
2. Dacă directorul nu există (task mutat de completion-handler), scrie în `~/.nexus/workspace/completed/{task_id}/JUDGE.md`

#### PASUL 8: Complete (or Retry on Failure)

**8a. On SUCCESS. Atomic ordering (MANDATORY):**

1. Write `.done` marker FIRST (race guard against timeout-watchdog):
```bash
touch ~/.nexus/workspace/active/{task_id}/.done
```

2. THEN update PROGRESS.md → `status: DONE`.

**Log state transition** (MANDATORY. use log-transition.sh with .claimed guard):
```bash
if [ ! -f ~/.nexus/workspace/active/{task_id}/.claimed ] && \
   [ ! -f ~/.nexus/workspace/completed/{task_id}/.claimed ]; then
    bash ~/.nexus/v2/lib/log-transition.sh "{task_id}" "STARTED" "DONE" "genie"
fi
```
Note: `.claimed` is written by fswatch dispatch-handler only. If it exists, fswatch handled logging. skip manual log. If absent, the task was executed in-process (Agent() call) and GENIE must log. Check both active/ and completed/ paths because completion-handler may have moved the task directory before Pasul 8 runs. Always use `log-transition.sh` for state transitions (enforces terminal-state guard and concurrency safety via mkdir-based atomic lock).

Raporteză rezultatele utilizatorului.

**8b. On FAILED. Retry Protocol:**

When a dispatched task reaches FAILED status, GENIE classifies the error and decides retry vs escalate.

**Step 1: Classify error** from error.log or PROGRESS.md error field:
- `transient`: keywords "timeout", "rate limit", "network", "connection", "503", "429" -> auto-retry with backoff
- `operator`: keywords "permission denied", "command not found", "not installed", "EACCES" -> escalate to Pafi immediately, NO retry
- `permanent`: everything else (syntax error, wrong approach, missing dependency) -> retry with failure context injected

**Step 2: Check retry budget**:
Read `retry_count` and `max_retries` from PROGRESS.md (defaults: retry_count=0, max_retries=2).
- If `retry_count >= max_retries`: task is permanently FAILED. Escalate to Pafi.
- If `error_class = operator`: escalate to Pafi immediately regardless of retry_count.

**Step 3: Execute retry**:
1. Increment `retry_count` in PROGRESS.md.
2. Set `error_class` in PROGRESS.md (transient/permanent/operator).
3. Set `last_failure_reason` in PROGRESS.md with the error message.
4. Log state transition: `bash ~/.nexus/v2/lib/log-transition.sh "{task_id}" "FAILED" "RETRYING" "genie"`
5. For `permanent` errors: inject failure context into DISPATCH.md:
   ```
   ## Retry Context
   Previous attempt failed: {last_failure_reason}
   Retry #{retry_count}. Address the failure above.
   ```
   This gives the LLM agent new information to course-correct (not a blind re-dispatch).
6. For `transient` errors: wait backoff (1s * 2^retry_count) then re-dispatch with same DISPATCH.md.
7. Reset PROGRESS.md status to DISPATCHED and re-enter Pasul 6.

**PROGRESS.md retry fields** (add to template on task creation):
```yaml
retry_count: 0
max_retries: 2
last_failure_reason: ""
error_class: ""
```

---

### CMD: logs

**Usage**: `/nexusos logs [agent] [N]`

Agent poate fi: `genie`, `delphi`, `sentinel`, `nexus`, `all`

Log paths:
- `genie` → `~/.nexus/logs/genie-heartbeat.log`
- `delphi` → `~/.nexus/logs/delphi-heartbeat.log`
- `sentinel` → `~/.nexus/logs/sentinel-health.log`
- `nexus` → `~/.nexus/workspace/logs/nexus.log`
- fără agent sau `all` → toate 4, câte 10 linii fiecare

```bash
tail -N ~/.nexus/logs/{agent}-heartbeat.log
```

Default N = 20.

---

### CMD: kick

Trigger manual GENIE heartbeat:

```bash
launchctl kickstart -k gui/$(id -u)/com.nexus.genie-heartbeat
```

Confirmă:
```
GENIE heartbeat triggered.
Urmărește: /nexusos logs genie 30
```

---

### CMD: smoke

```bash
~/.nexus/scripts/nexus-smoke-test.sh 2>&1 | tail -20
```

Afișează rezultatul și rezumă: PASS / FAIL / câte checks au trecut.

---

### CMD: tasks

```bash
echo "=== ACTIVE ===" && ls -la ~/.nexus/workspace/active/ 2>/dev/null
echo "=== COMPLETED ===" && ls ~/.nexus/workspace/completed/ 2>/dev/null
```

Pentru fiecare task activ, citește `PROGRESS.md` și afișează:
`{task_id}: {status} | {agent} | {updated_at} | {completion_pct}%`

---

### CMD: agents

Citește `~/.nexus/v2/config/agent-registry.yaml` și afișează toți agenții:

```
NexusOS Agents — {timestamp}

AGENT        STATUS     SKILLS  MODEL           ROLE
-----------  ---------  ------  --------------  --------------------------
GENIE        active     13      opus-4-6        orchestrator
TECH         active     13      sonnet-4-6      development [builder, fixer, integrator, pipeliner, product]
DELPHI       active     30      sonnet-4-6      research
MERCURY      active     25      sonnet-4-6      bi-marketing [seo, content, ads, smsads, outreach]
ECHELON      active     23      gemini-flash    intelligence [collector, enricher, scout, synthesizer, dispatcher]
SENTINEL     active     13      ollama-qwen2.5  ops-security
CONCIERGE    active     22      sonnet-4-6      personal-assistant
HEALTH       active     13      sonnet-4-6      health-longevity
TRAVEL       active     17      sonnet-4-6      travel-specialist
AUCTION      deployed   15      sonnet-4-6      eu-industrial-auctions
LIS          active     —       sonnet-4-6      telegram-pa
```

Dacă un agent are `status: degraded` sau `offline` → marchează cu `[!]` și afișează fallback.

---

## Output Rules

- Răspunsuri scurte, structurate, fără introduceri lungi.
- Statusurile se colorează textual: `GREEN` / `YELLOW` / `RED`.
- Dacă o comandă eșuează (script nu există, permisiuni etc.) → raportează exact eroarea și calea.
- Nu modifica niciun fișier de configurație NexusOS — doar citit și exec.
- Nu trimiți task-uri cu budget > $2.00 fără confirmare explicită din partea lui Pafi (IL-3).

## Examples

```
/nexusos                                                  — status instant
/nexusos agents                                           — lista completă agenți
/nexusos dispatch "Research concurenți SMSads în Kenya"   — auto-classify → delphi
/nexusos dispatch "Audit SEO site albastru.ro"            — auto-classify → mercury
/nexusos dispatch "Fix bug în heartbeat-tech.sh" tech     — direct route → tech
/nexusos dispatch "Find flight BUH to AMS 10 May"         — auto-classify → travel
/nexusos logs genie 30
/nexusos kick
/nexusos smoke
/nexusos tasks
```

---

## Dispatch Model Decision (2026-04-01)
GENIE uses TWO dispatch paths:
1. **File dispatch** (via nexus-task-create.sh): Creates workspace files. fswatch daemon auto-claims and routes. Use for all tasks that should be tracked in the workspace.
2. **In-process dispatch** (via Agent() call): GENIE executes the agent directly in the current session. Use when GENIE needs the result immediately (e.g., judge step, quick queries).

The .claimed marker distinguishes the two paths for logging purposes. This is the canonical model; no further consolidation needed.

---

## Appendix A: Manual Workspace Creation (Fallback)

Use ONLY if `~/.nexus/scripts/nexus-task-create.sh` is unavailable.

**A1. Creează directorul**:
```bash
mkdir -p ~/.nexus/workspace/active/{task_id}/
```

**A2. Scrie DISPATCH.md** (escape descrierea cu YAML block scalar `>` pentru a preveni injection):
```yaml
---
task_id: {task_id}
status: DISPATCHED
assigned_agent: {agent}
complexity: {LOW/MEDIUM/HIGH}
description: >
  {descriere — pe linie nouă, indentată, fără ghilimele raw}
timeout_s: {timeout_s}
budget_usd: {budget}
dispatched_at: {ISO timestamp}
dispatched_by: genie
---
```
Body: descrierea completă a task-ului cu context expandat (constraints, referințe Cortex relevante).

**A3. Scrie PROGRESS.md**:
```yaml
---
task_id: {task_id}
status: DISPATCHED
assigned_agent: {agent}
started_at: {ISO timestamp}
updated_at: {ISO timestamp}
completion_pct: 0
---
```

**A4. Log state transition** (MANDATORY):
```bash
mkdir -p ~/.nexus/workspace/logs/
printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "{task_id}" "NEW" "DISPATCHED" "genie" >> ~/.nexus/workspace/logs/state-transitions.log
```
