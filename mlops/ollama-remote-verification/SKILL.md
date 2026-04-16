---
name: ollama-remote-verification
description: Verify a local or remote Ollama instance, enumerate models, and run a smoke test safely over SSH. Includes a reliable pattern for remote checks on Hetzner/VPS hosts and avoids brittle nested stdin parsing.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Ollama, SSH, Verification, Hetzner, VPS, Local-LLM]
---

# Ollama Remote Verification

Use when you need to confirm that an Ollama instance is actually live on a local machine or remote VPS and that at least one model can answer a real prompt.

## When to use
- User says Ollama is installed on a server and wants live verification
- You need fallback-model readiness before switching away from hosted models
- You need a quick inventory of remote models and service health

## Procedure

### 1) Verify connectivity to the host
Use SSH first. Do not assume the Ollama port is exposed publicly.

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 user@host 'echo CONNECTED && hostname && command -v ollama || true'
```

If this works, prefer querying Ollama through localhost on the remote machine.

### 2) Query the remote Ollama API through SSH
Use localhost on the remote host:

```bash
ssh -o BatchMode=yes user@host 'curl -i --max-time 5 http://127.0.0.1:11434/api/tags'
```

Expected:
- HTTP/1.1 200 OK
- JSON body with `models`

### 3) If parsing is needed, inspect raw output first
If a JSON parser fails, do not assume Ollama is broken. First print raw output and check for:
- empty body
- shell quoting issues
- mixed stdout/stderr
- broken pipeline input

Also collect process/service state:

```bash
ssh user@host '
ps aux | grep -i "[o]llama" || true
(systemctl --no-pager --full status ollama 2>&1 | sed -n "1,40p") || true
'
```

### 4) Smoke test a real model
Prefer a minimal deterministic prompt:

```bash
ssh -o BatchMode=yes user@host "curl -s --max-time 180 http://127.0.0.1:11434/api/generate -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-coder:30b\",\"prompt\":\"Reply with exactly: OLLAMA_OK\",\"stream\":false}'"
```

Success criteria:
- JSON response returns
- `response` matches expected text
- `done: true`

### 5) Inventory useful model tiers
When reporting, group models by role:
- tiny/fast gate model
- general workhorse
- coding model
- heavy strategic/reasoning model
- embeddings model

## Important experiential findings

### Avoid brittle nested stdin parsing over SSH
A failed pattern encountered in practice:
- generating JSON with a here-doc Python block
- piping into curl
- then piping into another here-doc Python block

This can lead to empty stdin / JSON parse failures even though Ollama itself is healthy.

If that happens, simplify immediately:
- first print raw `curl` output
- then use a direct one-line JSON payload for the smoke test
- only add parsing after raw output is confirmed

### Prefer localhost queries on the remote host
Even if direct `http://host:11434` checks fail externally, Ollama may be healthy and intentionally bound to localhost. SSH + localhost curl is the reliable verification path.

## Reporting template
- SSH access: working / failed
- Hostname
- Ollama binary path
- Service state
- Model count
- Notable models by tier
- Smoke test result
- Recommended fallback routing

## Benchmarking for fallback selection
Use this when the user does not just want to know whether Ollama works, but which model is safe to rely on when premium credits are exhausted.

### Goal
Choose the best local/cloud Ollama fallback without sacrificing conversation quality or waiting unreasonably long for responses.

### Recommended benchmark sequence
Test from the strongest candidate down to smaller models. Example order:
- `hermes3:70b`
- other 70B / premium local models
- strong coding / reasoning mid-tier models like `qwen3-coder:30b`
- general workhorses like `gemma4:26b` / `gemma3:27b`
- small utility models like `llama3.1:8b`

### Two-stage benchmark

#### 1) Reachability + latency probe
Run a minimal deterministic prompt first:

```bash
ssh -o BatchMode=yes user@host "curl -s --max-time 180 http://127.0.0.1:11434/api/generate -H 'Content-Type: application/json' -d '{\"model\":\"MODEL_NAME\",\"prompt\":\"Reply with exactly: READY\",\"stream\":false}'"
```

Capture:
- total duration
- whether the instruction was followed exactly
- whether the model timed out or stalled

#### 2) Quality-under-constraint probe
Then test a realistic operator prompt with strict formatting, multiple constraints, and a role-relevant task.

Good pattern:
- require a short answer
- require exact sections or bullets
- require tone and audience constraints
- use a task similar to the actual production use case (chief-of-staff, planning, synthesis, crisis memo, etc.)

Example criteria to evaluate:
- follows required structure exactly
- stays within length limits
- does not invent nonexistent models / entities / assumptions
- remains concrete, calm, and operational
- gives usable output without excess fluff

### Decision rule
Rank by:
1. quality / instruction discipline
2. latency
3. factual restraint

Reject models that:
- hallucinate important details
- miss format constraints repeatedly
- exceed acceptable conversational latency even if output quality is decent

### Practical finding from live testing
A model can be “good” in absolute quality but still be a bad fallback if it takes 2-4+ minutes for a short structured response.

In one live Hetzner benchmark, this pattern appeared:
- `qwen3-coder:30b` = strong practical fallback: usable structure + acceptable latency
- `gemma4:26b` = decent quality but too slow for fluid conversation
- `hermes3:70b` = coherent but too slow for chief-of-staff live dialogue
- `llama3.1:8b` = fast but too weak / too hallucination-prone for strategic continuity

Additional live finding for coding workloads on the same Hetzner host:
- `qwen3-coder-next:latest` (79.7B Q4_K_M, ~51.7 GB on disk) performed surprisingly well as a local coding candidate on a 251 GiB RAM Hetzner machine.
- Example timings from live coding probes on the same-host Ollama setup:
  - codegen prompt: ~11.5s total
  - Python debugging prompt: ~28.8s total
- `qwen3-coder:30b` remained faster on some small tasks (~6s codegen) but should still be compared against `qwen3-coder-next:latest` on debugging and instruction-following before final promotion.

Do not hardcode these conclusions globally. Re-test on the actual machine and current load, but use them as a strong prior.

## Coding-specific benchmark extension
Use this when the user wants the best local coding fallback, not just general conversation fallback.

### Scope
Benchmark only the models that are local to the execution domain you are testing. If Hermes and Ollama are on the same Hetzner host, do NOT mix MacM4 coding agents into the local-Ollama benchmark.

### Capacity check before testing
Run these first on the target host:

```bash
free -h
swapon --show || true
ollama ps || true
ps -o pid,ppid,%mem,rss,vsz,etime,cmd -C ollama || true
curl -s http://127.0.0.1:11434/api/tags
```

Interpretation:
- If available RAM is very high (e.g. >200 GiB available on a 251 GiB host), 70B-80B Q4 coding models are realistic to test.
- Use `ollama ps` to see which model is currently resident and its memory footprint.
- Same-host Hermes→Ollama testing removes most network noise, so measured latency is mostly inference latency.

### Coding benchmark suites
At minimum run two suites per model:

#### 1) Codegen probe
Prompt pattern:
- require code only
- require a tiny but complete script
- require stdin / JSON / fallback behavior
- no prose allowed

Good example:
- “Return only Python code. Write a small script that reads JSON from stdin and prints the value of key `status`. If missing, print `UNKNOWN`. No explanations.”

#### 2) Debugging probe
Prompt pattern:
- real traceback or bug pattern
- strict length cap
- exact response structure
- require root cause, minimal fix, verification

Good example:
- “Give exactly 3 bullets: Root cause, Minimal fix, Verification.”

### Coding benchmark decision rule
Rank by:
1. debugging quality
2. instruction-following discipline
3. code validity / minimalism
4. latency

Reject models that:
- hallucinate APIs, files, or nonexistent context
- ignore code-only constraints
- cannot identify the real root cause in simple debugging probes
- are too slow for live iterative coding even if the answer is decent

### Shell / pipeline pitfalls found in practice
When building remote benchmark scripts:
- quote `-H 'Content-Type: application/json'` correctly; dropping the quotes can break the curl invocation
- if you pipe Python JSON generation into curl, the pipeline exit code may reflect the producer side and show non-zero RC values even when Ollama returned a valid JSON response
- do not treat an `RC:6` style shell artifact as immediate model failure without inspecting the actual Ollama output
- use `set -uo pipefail` with care; for benchmark logging scripts, prefer explicit response capture and explicit error markers over brittle shell pipeline assumptions
- for multi-line Python benchmark scripts sent over SSH, nested here-doc quoting is fragile and can silently corrupt the script; a safer pattern is to base64-encode the script locally, decode it remotely into `/tmp/<name>.py`, then launch it with `nohup python3 ... &`
- immediately verify launch by checking all three: the script file exists, the log file exists and has a start marker, and `ps` shows the Python process still running

### Practical capacity rule: "fits" is not the same as "usable"
On large-RAM Ollama hosts, separate two questions:
1. Can the model be loaded?
2. Is it fast enough for the actual workflow?

Live finding on a ~251 GiB Hetzner host:
- 70B–80B Q4 models fit comfortably in RAM
- but `llama3.3:70b`, `gemma4:26b`, and `hermes3:70b` were still too slow for live coding iteration despite fitting
- therefore the practical max coding size should be chosen by latency-under-debugging-tests, not by memory headroom alone

Use this decision rule when reporting capacity:
- `maximum possible size` = what the host can load without memory pressure
- `maximum practical coding size` = largest model that still gives acceptable iterative latency on codegen + debugging probes

Do not report only RAM fit; report both thresholds explicitly.

## Example summary
- SSH access works to `user@host`
- Ollama active on `127.0.0.1:11434`
- `/api/tags` returns model inventory
- Smoke test passed on `qwen3-coder:30b`
- Use workhorse + coding + heavy model triad for fallback planning
- If credits are nearly exhausted, benchmark live before promoting any Ollama model to primary fallback

## Do not
- Do not rely on public port exposure as the first verification method
- Do not assume JSON parse failure means Ollama is down
- Do not close the task without a real model smoke test
- Do not promote a model to conversation fallback based only on "it answered once"; benchmark structure + latency + hallucination risk