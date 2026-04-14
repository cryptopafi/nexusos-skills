---
name: grill-me
description: "Interview the user relentlessly about a plan, design, or decision until reaching shared understanding. Resolves each branch of the decision tree one-by-one, providing recommended answers. Use when user says '/grill-me', 'grill me', 'stress-test this plan', 'challenge my design', 'interview me about this', or wants to validate a decision before implementation."
argument-hint: "[topic or plan to grill]"
---

# /grill-me — Decision Tree Interviewing

Interview the user relentlessly about every aspect of their plan, design, or decision until reaching shared understanding. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one.

## Arguments

The user provides a topic, plan, or design to be grilled on.

**Input validation:**
- If no argument is provided and no prior context exists in the conversation, ask: "What plan, design, or decision do you want to stress-test?"
- If the argument is a single word with no elaboration, ask for one sentence of context before proceeding.
- If the argument references a file that doesn't exist or a plan that can't be found, say so explicitly and ask the user to paste or describe the content directly.
- Do not attempt to infer a topic from noise or greet-style input — ask.

## Error Contract

| Condition | Behavior |
|---|---|
| Empty / missing argument | Ask for topic before any other step |
| Referenced file not found | Report the missing path, ask user to provide content inline |
| User answers "I don't know" to a decision | Record as DEFERRED, continue tree, revisit at Step 5 |
| User gives a contradictory answer | Flag the contradiction explicitly (see Step 3 → Contradictions), do not silently accept |
| User signals abandonment ("stop", "skip this", "never mind") | Acknowledge, emit partial summary of resolved decisions so far, stop gracefully |
| Decision tree expands beyond 15 nodes | Warn user, ask whether to continue or scope-limit the session |

## Execution

### Step 0: PromptForge Gate

Before mapping any decisions, classify the session and optimize the interview driver.

**Classification:**
| Type | Criteria | PromptForge path |
|---|---|---|
| STANDARD | Single domain, clear scope, <5 decisions expected | F0→F1→F2→F3→F5→F6 |
| COMPLEX | Multi-domain, architecture/business model, >5 decisions, high-stakes | F0→F1→F2(full)→F3→F4→F5→F6 |

**Technique selection for decision interviews (Pas 3 from PROMPTING.md):**
- Always: **C-046 Flipped Interaction** (user answers, AI asks) + **C-051 Alternative Approaches** (A/B/C options)
- COMPLEX add: **C-044 Cognitive Verifier** (break into sub-questions) + **C-065 Self-Calibration** (confidence check on recommendations)
- High-stakes add: **Adversarial Framing** (challenge each recommendation before presenting)

**Execution:**
1. Emit: `🔧 PromptForge [STANDARD/COMPLEX] — grill-me session`
2. Apply selected techniques to the framing of decision questions (not to the topic itself)
3. Score F5: Claritate + Completitudine + Corectitudine + Focalizare + Adecvare (D1-D5, /100)
4. Gate: ≥75 → proceed | <75 → Self-Refine Loop (max 2 iter) → proceed
5. Emit VK: `✅ [PROMPTING] grill-me | class: {STANDARD/COMPLEX} | score: {X}/100 | techniques: {list}`

**Skip condition**: Topic is fully trivial (single yes/no decision with no dependencies) → skip PromptForge, go directly to Step 1.

---

### Step 1: Understand the Subject

Read any referenced files, plans, or context. If the subject is a codebase design, explore the codebase first. Build a mental model of the decision space before asking anything.

### Step 2: Map the Decision Tree

Identify ALL decisions that need to be made. Group them by dependency — some decisions block others. Order them so that foundational decisions come first and dependent decisions come after.

For each decision, prepare:
- **Options** (2-3 viable approaches, labeled A/B/C)
- **Pro/Con** for each option
- **Your recommended answer** with reasoning
- **The question** — direct, specific, one decision at a time

### Step 3: Walk the Tree

Present ONE decision at a time. Format:

```
### Decizia N: [Topic]

[Context — why this decision matters]

**Opțiunea A — [Name]**
- Pro: ...
- Con: ...

**Opțiunea B — [Name]**
- Pro: ...
- Con: ...

**Recomandarea mea: [A/B/C]** — [reasoning]

**Întrebarea: [Direct question requiring a choice]**
```

Rules:
- ONE decision per message. Do not batch.
- Wait for the user's answer before proceeding.
- If the user's answer is unclear, probe deeper — do not assume.
- If a question can be answered by exploring the codebase, explore instead of asking.
- Track answered decisions with a running table.
- When a decision reveals new sub-decisions, add them to the tree.

**Contradictions:** If the user's answer contradicts a previously resolved decision, stop and surface it:
> "Răspunsul tău la D[N] contrazice D[M] unde ai ales [X]. Hai să reconciliem înainte să continuăm."
Re-open the earlier decision if needed. Do not silently accept the contradiction.

**Abandonment:** If the user says "stop", "skip", "enough", or equivalent at any point during the tree walk, emit a partial summary of all decisions resolved so far (same format as Step 5) and stop. Do not continue asking questions.

### Step 4: Handle Dependencies

If decision N depends on decision M which hasn't been answered yet, say so explicitly:
> "Asta depinde de Decizia M. Hai să rezolvăm mai întâi M."

Then redirect to M.

### Step 5: Summarize

After all decisions are resolved, present a complete summary table:

```
## Toate deciziile — Stare finală

| # | Decizie | Răspuns | Status |
|---|---------|---------|--------|
| D1 | ... | ... | ✅ |
| D2 | ... | ... | ✅ |
| D3 | ... | ... | ⏸ DEFERRED |
```

Status values: ✅ resolved, ⏸ DEFERRED (user said "I don't know"), ⚠️ needs follow-up.

Then ask: "Toate deciziile confirmate. Trecem la implementare?"

## Principles

- Be relentless — do not let vague answers pass. Probe until specific.
- Provide recommended answers — the user can disagree but should have a starting point.
- Respect dependencies — resolve blocking decisions first.
- Use the user's language — match Romanian/English based on their responses.
- One branch at a time — depth-first, not breadth-first.