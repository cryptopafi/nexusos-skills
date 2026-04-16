---
name: github-private-repo-file-audit
description: Audit a specific filename or config doc across all private GitHub repositories for an authenticated account, using a reliable clone-first workflow when GitHub API tree/code search is incomplete.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, audit, private-repos, gh, git, USER.md]
    related_skills: [github-auth, github-repo-management]
---

# GitHub Private Repo File Audit

Use this when the user asks questions like:
- "Check `USER.md` in all my private repos"
- "Find every `AGENTS.md`/`SOUL.md`/`README` variant across my repos"
- "Show me which repos contain profile files and summarize differences"

This skill is optimized for **private repos** and avoids false negatives from GitHub API/search limitations.

## Why this workflow exists

In practice, these methods can fail or mislead when auditing many private repos:

1. `gh api repos/OWNER/REPO/git/trees/BRANCH?recursive=1`
   - Large trees may return JSON that gets truncated or malformed in tool output.
   - You may see parse errors like `Invalid control character at char 20000`.

2. `gh api search/code`
   - Can miss results for private repos, case variants (`USER.md` vs `user.md`), or return inconsistent coverage.
   - Do **not** trust code search alone for exhaustive audits.

Because of that, the **reliable method is clone-first, then local filesystem scan**.

## Recommended workflow

### 1. Confirm GitHub auth

Use the `github-auth` skill if needed.

Quick check:

```bash
gh auth status
git --version
```

### 2. List private repos

```bash
gh repo list <owner> --visibility private --limit 200 --json nameWithOwner
```

If you need default branches too:

```bash
gh repo list <owner> --visibility private --limit 200 --json nameWithOwner,defaultBranchRef,isArchived
```

### 3. Clone each repo shallowly to a temp workspace

Prefer SSH if `gh auth status` says git protocol is SSH.

```bash
BASE=~/tmp/github-private-scan
mkdir -p "$BASE"

git clone --depth 1 git@github.com:OWNER/REPO.git "$BASE/REPO"
```

Notes:
- Use `--depth 1` for speed.
- Delete stale partial clones before retrying.
- Skip `.git/` during scanning.

### 4. Scan locally for the filename, case-insensitive

Python pattern:

```python
import os

for root, dirs, files in os.walk(repo_dir):
    dirs[:] = [d for d in dirs if d != '.git']
    for f in files:
        if f.lower() == 'user.md':
            path = os.path.join(root, f)
```

This catches:
- `USER.md`
- `user.md`
- mixed-case variants

### 5. Read previews and summarize

For each match, extract:
- repo name
- relative path
- line count
- first 20–25 lines preview
- inferred profile type (owner profile / agent persona / template / function-specific profile)

### 6. Report at two levels

Always provide:
1. **inventory** — which repos contain the file and where
2. **meaning** — what those files represent conceptually

Good summary buckets:
- owner/user profile
- agent persona profile
- role-specific profile
- generic template
- backup/archive duplicate

## Suggested execution pattern with Hermes tools

Best reliable stack:
- `skill_view(github-auth)` if needed
- `terminal()` or `execute_code()` to list repos and clone
- `read_file()` for important matched files you want to quote accurately
- `todo()` if the audit spans many repos

## Heuristics for summarizing profile files

When auditing files like `USER.md`, classify them by these questions:

- Is this about the human owner, or about an agent persona?
- Is it generic, or scoped to a function (ops/marketing/legal/finance/etc.)?
- Does it define communication style?
- Does it define approval boundaries?
- Does it define projects/business priorities?
- Does it define environment/infrastructure constraints?
- Is it canonical, or obviously backup/archive/history?

## Common pitfalls

- Do not trust GitHub tree API alone for large repos.
- Do not trust GitHub code search alone for exhaustive private-repo audits.
- Do not forget case-insensitive filename matching.
- Do not treat backup/archive copies as separate living profiles unless the user asks for historical comparison.
- Do not stop at file inventory; the user usually wants a synthesis of identity/profile differences.

## Minimal reusable Python outline

```python
from hermes_tools import terminal
import json, os

repos = json.loads(terminal(
    "gh repo list OWNER --visibility private --limit 200 --json nameWithOwner",
    timeout=120,
)["output"])

base = os.path.expanduser('~/tmp/github-private-scan')
os.makedirs(base, exist_ok=True)
results = []

for repo in repos:
    full = repo['nameWithOwner']
    name = full.split('/')[-1]
    target = os.path.join(base, name)
    terminal(f"rm -rf {target}", timeout=120)
    clone = terminal(f"git clone --depth 1 git@github.com:{full}.git {target}", timeout=300)
    if clone['exit_code'] != 0:
        results.append({'repo': full, 'error': clone['output'][:500]})
        continue

    matches = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d != '.git']
        for f in files:
            if f.lower() == 'user.md':
                path = os.path.join(root, f)
                rel = os.path.relpath(path, target)
                with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                    lines = fh.read().splitlines()
                matches.append({
                    'path': rel,
                    'line_count': len(lines),
                    'preview': '\n'.join(lines[:25]),
                })

    results.append({'repo': full, 'matches': matches})
```

## Output format recommendation

Use this structure in the final answer:

- total repos scanned
- repos with matches
- repos without matches
- detailed list of matching repos + paths
- conceptual synthesis
- duplicates/backups note
- strongest conclusion / recommended next step

## Best-practice conclusion

For exhaustive audits of a file across private repos:
- use `gh repo list` to enumerate,
- shallow clone each repo,
- scan locally,
- then use file reads for the key matches.

This is more reliable than GitHub tree API or code search when completeness matters.
