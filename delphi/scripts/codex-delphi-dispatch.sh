#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: codex-delphi-dispatch.sh --topic TEXT [--depth D1|D2|D3|D4] [--budget USD] [--timeout SECONDS] [--model MODEL] [--backend auto|codex|claude|python] [--store-cortex] [--dry-run]

When --depth is omitted, the dispatcher auto-classifies D1-D4 using Delphi Pro intake rules.
EOF
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

topic=""
depth=""
depth_source="auto"
budget=""
timeout_seconds=""
model="claude-sonnet-4-6"
backend="auto"
store_cortex=0
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic)
      [[ $# -ge 2 ]] || die "--topic requires a value"
      topic="$2"
      shift 2
      ;;
    --depth)
      [[ $# -ge 2 ]] || die "--depth requires a value"
      depth="$2"
      depth_source="explicit"
      shift 2
      ;;
    --budget)
      [[ $# -ge 2 ]] || die "--budget requires a value"
      budget="$2"
      shift 2
      ;;
    --timeout)
      [[ $# -ge 2 ]] || die "--timeout requires a value"
      timeout_seconds="$2"
      shift 2
      ;;
    --model)
      [[ $# -ge 2 ]] || die "--model requires a value"
      model="$2"
      shift 2
      ;;
    --backend)
      [[ $# -ge 2 ]] || die "--backend requires a value"
      backend="$2"
      shift 2
      ;;
    --store-cortex)
      store_cortex=1
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$topic" ]] || { usage; die "--topic is required"; }

classify_depth() {
  python3 - "$topic" <<'PY'
import re
import sys

topic = sys.argv[1]
text = topic.lower()
tokens = set(re.findall(r"[a-z0-9][a-z0-9._+-]*", text))

def has_any(phrases):
    return any(phrase in text for phrase in phrases)

d4_phrases = (
    " d4 ", "depth d4", "--depth d4", "exhaustive", "investment-grade",
    "pafi-grade", "due diligence", "production lock", "final lock",
    "final decision", "full deep dive", "full market map",
)
d3_phrases = (
    "deep research", "strategic synthesis", "competitive intel",
    "trend analysis", "what's the landscape", "state of the art",
    "architecture decision", "provider selection", "source-backed",
)
d2_phrases = (
    "research", "compare", "comparison", "evaluate", "assessment",
    "multi-factor", "multiple perspectives", "technology landscape",
    "options", "alternatives",
)
d1_starters = {"what", "who", "when", "where", "which"}
d1_phrases = ("quick check", "quick lookup", "single fact", "what is", "version of")

complexity_score = 0
if has_any(("vs", "compare", "tradeoff", "multi-angle", "different fields", "cross-domain")):
    complexity_score += 1
if has_any(("contradict", "contested", "evolving", "uncertain", "debate")):
    complexity_score += 1
if has_any(("latest", "current", "today", "2026", "regulatory", "market shift")):
    complexity_score += 1
if has_any(("financial", "legal", "strategic", "production", "high-stakes", "investment")):
    complexity_score += 1
if has_any(("academic", "peer-reviewed", "paper", "papers", "clinical", "evidence")):
    complexity_score += 1

if has_any(d4_phrases) or "d4" in tokens:
    print("D4")
elif len(tokens) <= 8 and (tokens & d1_starters or has_any(d1_phrases)):
    print("D1")
elif complexity_score >= 3 or has_any(d3_phrases) or "d3" in tokens:
    print("D3")
elif has_any(d2_phrases):
    print("D2")
else:
    print("D2")
PY
}

if [[ -z "$depth" ]]; then
  depth="$(classify_depth)"
fi

[[ "$depth" =~ ^D[1-4]$ ]] || die "--depth must be D1, D2, D3, or D4"
[[ "$backend" =~ ^(auto|codex|claude|python)$ ]] || die "--backend must be auto, codex, claude, or python"

case "$depth" in
  D1)
    default_timeout=300
    default_budget="0.01"
    max_turns=8
    complexity="low"
    ;;
  D2)
    default_timeout=900
    default_budget="0.15"
    max_turns=15
    complexity="medium"
    ;;
  D3)
    default_timeout=1800
    default_budget="0.80"
    max_turns=35
    complexity="high"
    ;;
  D4)
    default_timeout=3600
    default_budget="5.00"
    max_turns=80
    complexity="high"
    ;;
esac

if [[ -z "$budget" ]]; then
  budget="$default_budget"
fi
[[ "$budget" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "--budget must be numeric"

if [[ -z "$timeout_seconds" ]]; then
  timeout_seconds="$default_timeout"
fi
[[ "$timeout_seconds" =~ ^[0-9]+$ ]] || die "--timeout must be integer seconds"

home_dir="${HOME:-/Users/pafi}"
plugin_dir="$home_dir/.claude/plugins/delphi"
nexus_agent_dir="$home_dir/.nexus/agents/delphi"
nexus_v2_dir="$home_dir/.nexus/v2/agents/delphi"
python_delphi_dir="$home_dir/repos/delphi"
workspace_root="$home_dir/.nexus/workspace/codex-delphi"
timestamp="$(date -u +%Y%m%d-%H%M%S)"
task_id="codex-delphi-$timestamp-$$"
task_dir="$workspace_root/$task_id"

[[ -d "$plugin_dir" ]] || die "Delphi plugin missing: $plugin_dir"
[[ -f "$plugin_dir/agents/delphi.md" ]] || die "Delphi agent prompt missing: $plugin_dir/agents/delphi.md"
[[ -d "$nexus_agent_dir" ]] || die "Nexus Delphi agent missing: $nexus_agent_dir"
if [[ "$backend" == "claude" ]]; then
  command -v claude >/dev/null 2>&1 || die "claude CLI not found"
fi
if [[ "$backend" == "python" || "$backend" == "auto" || "$backend" == "codex" ]]; then
  [[ -f "$python_delphi_dir/research.py" ]] || die "Python Delphi missing: $python_delphi_dir/research.py"
fi
if [[ "$backend" == "auto" || "$backend" == "codex" ]]; then
  [[ -f "$python_delphi_dir/codex_runner.py" ]] || die "Codex Delphi runner missing: $python_delphi_dir/codex_runner.py"
fi

mkdir -p "$task_dir"

cat > "$task_dir/DISPATCH.md" <<EOF
task_id: "$task_id"
assigned_agent: "delphi"
source_agent: "codex"
depth: "$depth"
depth_source: "$depth_source"
complexity: "$complexity"
budget_usd: $budget
backend: "$backend"
timeout_s: $timeout_seconds
max_turns: $max_turns
topic: |
$(printf '%s\n' "$topic" | sed 's/^/  /')
output_contract:
  output_md: "$task_dir/output.md"
  execution_log: "$task_dir/EXECUTION.log"
  cortex_collection: "research"
EOF

cat > "$task_dir/PROGRESS.md" <<EOF
status: DISPATCHED
agent: "delphi"
source_agent: "codex"
task_id: "$task_id"
started_at: null
updated_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
completed_at: null
output_location: "$task_dir"
confidence: null
spent_usd: 0.00
EOF

prompt="$(cat <<EOF
You are running Delphi Pro research for Codex.

Read these files first:
- $plugin_dir/agents/delphi.md
- $nexus_agent_dir/SOUL.md
- $nexus_v2_dir/iron-laws.md
- $task_dir/DISPATCH.md

Execute a Delphi research job with:
- topic: $topic
- depth: $depth
- depth_source: $depth_source
- budget_usd: $budget
- requester: codex

Write the final result to:
- $task_dir/output.md

Output requirements:
- Include methodology, findings, sources, confidence, gaps, and next steps.
- For D2+, include a Source Coverage Report if available.
- For D3/D4, follow Delphi critic/EPR rules; if critic cannot run, mark output INCOMPLETE instead of inventing EPR.
- Do not edit Delphi plugin files.
- Do not expose secrets.
- If blocked, write output.md with status FAILED and exact non-secret reason.
EOF
)"

if [[ "$dry_run" -eq 1 ]]; then
  cat > "$task_dir/output.md" <<EOF
# Codex Delphi Dry Run

status: DRY_RUN
task_id: $task_id
depth: $depth
depth_source: $depth_source
backend: $backend
topic: $topic

Workspace and dispatch files were created. Execution was skipped.
EOF
  awk '{ if ($1=="status:") print "status: DRY_RUN"; else print }' "$task_dir/PROGRESS.md" > "$task_dir/PROGRESS.tmp"
  mv "$task_dir/PROGRESS.tmp" "$task_dir/PROGRESS.md"
  printf '%s\n' "$task_dir"
  exit 0
fi

allowed_tools="Read,Write,Bash,Glob,Grep,WebFetch,WebSearch,Agent,Skill,TodoWrite,mcp__cortex__cortex_search,mcp__cortex__cortex_store,mcp__cortex__cortex_find_procedure,mcp__cortex__cortex_list_collections,mcp__tavily__tavily_search,mcp__tavily__tavily_extract,mcp__tavily__tavily_crawl,mcp__tavily__tavily_research,mcp__tavily__tavily_map,mcp__brave-search__brave_web_search,mcp__brave-search__brave_local_search,mcp__exa__web_search_advanced_exa,mcp__arxiv__search_papers,mcp__arxiv__get_abstract,mcp__arxiv__download_paper,mcp__arxiv__read_paper,mcp__arxiv__citation_graph,mcp__arxiv__semantic_search,mcp__wikipedia__wiki_search,mcp__wikipedia__wiki_get_summary,mcp__wikipedia__wiki_get_article,mcp__openalex__search_works,mcp__openalex__search_authors,mcp__openalex__get_work,mcp__openalex__get_trends,mcp__youtube-transcript__get-transcript"
timeout_bin=""
if command -v gtimeout >/dev/null 2>&1; then
  timeout_bin="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  timeout_bin="timeout"
fi

awk '{ if ($1=="status:") print "status: IN_PROGRESS"; else if ($1=="started_at:") print "started_at: \"" strftime_utc "\""; else print }' strftime_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$task_dir/PROGRESS.md" > "$task_dir/PROGRESS.tmp"
mv "$task_dir/PROGRESS.tmp" "$task_dir/PROGRESS.md"

run_claude_backend() {
  if [[ -n "$timeout_bin" ]]; then
    "$timeout_bin" "$timeout_seconds" claude \
      --model "$model" \
      --max-turns "$max_turns" \
      --dangerously-skip-permissions \
      --allowedTools "$allowed_tools" \
      --add-dir "$plugin_dir" \
      --add-dir "$nexus_agent_dir" \
      --add-dir "$nexus_v2_dir" \
      --add-dir "$task_dir" \
      --print -p "$prompt" > "$task_dir/EXECUTION.log" 2>&1
  else
    claude \
      --model "$model" \
      --max-turns "$max_turns" \
      --dangerously-skip-permissions \
      --allowedTools "$allowed_tools" \
      --add-dir "$plugin_dir" \
      --add-dir "$nexus_agent_dir" \
      --add-dir "$nexus_v2_dir" \
      --add-dir "$task_dir" \
      --print -p "$prompt" > "$task_dir/EXECUTION.log" 2>&1
  fi
}

run_python_backend() {
  printf '\n--- PYTHON DELPHI FALLBACK ---\n' >> "$task_dir/EXECUTION.log"
  if [[ -n "$timeout_bin" ]]; then
    (
      cd "$python_delphi_dir"
      "$timeout_bin" "$timeout_seconds" python3 research.py "$topic" --type auto --depth "$depth" --cortex "http://localhost:6400" --collection research --json
    ) > "$task_dir/python-result.json" 2>> "$task_dir/EXECUTION.log"
  else
    (
      cd "$python_delphi_dir"
      python3 research.py "$topic" --type auto --depth "$depth" --cortex "http://localhost:6400" --collection research --json
    ) > "$task_dir/python-result.json" 2>> "$task_dir/EXECUTION.log"
  fi
  python_status=$?
  cat "$task_dir/python-result.json" >> "$task_dir/EXECUTION.log"
  if [[ "$python_status" -eq 0 ]]; then
    python3 - "$task_dir/python-result.json" "$task_dir/output.md" "$task_id" "$depth" "$backend" <<'PY'
import json
import pathlib
import sys

result_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
task_id = sys.argv[3]
depth = sys.argv[4]
backend = sys.argv[5]

try:
    result = json.loads(result_path.read_text(errors="replace"))
except json.JSONDecodeError:
    result = {"report": result_path.read_text(errors="replace")}

report = result.get("report")
if not report:
    report = "```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```"

output_path.write_text(
    f"# Codex Delphi Python Fallback Result\n\n"
    f"status: DONE\n"
    f"task_id: {task_id}\n"
    f"depth: {depth}\n"
    f"backend: {backend}\n"
    f"fallback_reason: Claude backend unavailable or skipped\n\n"
    f"{report}\n",
)
PY
  fi
  return "$python_status"
}

run_codex_backend() {
  printf '\n--- CODEX-NATIVE DELPHI BACKEND ---\n' >> "$task_dir/EXECUTION.log"
  local d4_owner_args=()
  if [[ "$depth" == "D4" ]]; then
    d4_owner_args=(--owner-approved-d4)
  fi
  if [[ -n "$timeout_bin" ]]; then
    if [[ "$store_cortex" -eq 1 ]]; then
      (
        cd "$python_delphi_dir"
        "$timeout_bin" "$timeout_seconds" python3 codex_runner.py \
          --topic "$topic" \
          --depth "$depth" \
          --task-dir "$task_dir" \
          --budget "$budget" \
          --cortex "http://localhost:6400" \
          --collection research \
          "${d4_owner_args[@]}" \
          --store-cortex
      ) > "$task_dir/codex-result.json" 2>> "$task_dir/EXECUTION.log"
    else
      (
        cd "$python_delphi_dir"
        "$timeout_bin" "$timeout_seconds" python3 codex_runner.py \
          --topic "$topic" \
          --depth "$depth" \
          --task-dir "$task_dir" \
          --budget "$budget" \
          --cortex "http://localhost:6400" \
          --collection research \
          "${d4_owner_args[@]}"
      ) > "$task_dir/codex-result.json" 2>> "$task_dir/EXECUTION.log"
    fi
  else
    if [[ "$store_cortex" -eq 1 ]]; then
      (
        cd "$python_delphi_dir"
        python3 codex_runner.py \
          --topic "$topic" \
          --depth "$depth" \
          --task-dir "$task_dir" \
          --budget "$budget" \
          --cortex "http://localhost:6400" \
          --collection research \
          "${d4_owner_args[@]}" \
          --store-cortex
      ) > "$task_dir/codex-result.json" 2>> "$task_dir/EXECUTION.log"
    else
      (
        cd "$python_delphi_dir"
        python3 codex_runner.py \
          --topic "$topic" \
          --depth "$depth" \
          --task-dir "$task_dir" \
          --budget "$budget" \
          --cortex "http://localhost:6400" \
          --collection research \
          "${d4_owner_args[@]}"
      ) > "$task_dir/codex-result.json" 2>> "$task_dir/EXECUTION.log"
    fi
  fi
  local codex_status=$?
  cat "$task_dir/codex-result.json" >> "$task_dir/EXECUTION.log" 2>/dev/null || true
  return "$codex_status"
}

set +e
if [[ "$backend" == "python" ]]; then
  run_python_backend
  run_status=$?
elif [[ "$backend" == "claude" ]]; then
  run_claude_backend
  run_status=$?
elif [[ "$backend" == "codex" ]]; then
  run_codex_backend
  run_status=$?
else
  run_codex_backend
  run_status=$?
fi
set -e

if [[ ! -f "$task_dir/output.md" ]]; then
  cat > "$task_dir/output.md" <<EOF
# Codex Delphi Execution Result

status: GENERATED_FROM_EXECUTION_LOG
task_id: $task_id
depth: $depth
backend: $backend
exit_code: $run_status

Claude did not create output.md directly, or Python backend was used. Captured response follows.

\`\`\`
$(tail -200 "$task_dir/EXECUTION.log")
\`\`\`
EOF
fi

if [[ "$run_status" -eq 0 ]]; then
  final_status="DONE"
else
  final_status="FAILED"
fi
if [[ "$run_status" -eq 0 && -f "$task_dir/codex-result.json" ]]; then
  codex_reported_status="$(python3 - "$task_dir/codex-result.json" <<'PY' 2>/dev/null || true
import json
import sys
try:
    print(json.load(open(sys.argv[1])).get("status", ""))
except Exception:
    pass
PY
)"
  if [[ "$codex_reported_status" == "BLOCKED_BY_D4_GATE" ]]; then
    final_status="BLOCKED_BY_D4_GATE"
  fi
fi

cat > "$task_dir/PROGRESS.md" <<EOF
status: $final_status
agent: "delphi"
source_agent: "codex"
task_id: "$task_id"
started_at: "$(date -u -r "$task_dir/EXECUTION.log" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
updated_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
completed_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
output_location: "$task_dir"
confidence: null
spent_usd: 0.00
exit_code: $run_status
EOF

if [[ "$store_cortex" -eq 1 && "$backend" != "codex" && "$backend" != "auto" && -s "$task_dir/output.md" ]]; then
  python3 - "$task_dir/output.md" "$task_id" "$depth" "$topic" <<'PY' > "$task_dir/cortex-payload.json"
import json
import pathlib
import sys

output_path = pathlib.Path(sys.argv[1])
task_id = sys.argv[2]
depth = sys.argv[3]
topic = sys.argv[4]
payload = {
    "text": f"CODEX DELPHI RESULT\nTASK: {task_id}\nDEPTH: {depth}\nTOPIC: {topic}\n\n" + output_path.read_text(errors="replace"),
    "collection": "research",
    "metadata": {
        "source_agent": "codex",
        "agent": "delphi",
        "task_id": task_id,
        "depth": depth,
        "genie_visible": True,
    },
}
print(json.dumps(payload))
PY
  curl -s -X POST http://localhost:6400/api/store -H 'Content-Type: application/json' --data-binary @"$task_dir/cortex-payload.json" > "$task_dir/cortex-store-response.json" || true
fi

printf '%s\n' "$task_dir"
exit "$run_status"
