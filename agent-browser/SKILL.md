---
name: agent-browser
description: Browser automation CLI for AI agents. Use when the user needs to interact with websites, including navigating pages, filling forms, clicking buttons, taking screenshots, extracting data, testing web apps, or automating any browser task. Triggers include requests to "open a website", "fill out a form", "click a button", "take a screenshot", "scrape data from a page", "test this web app", "login to a site", "automate browser actions", or any task requiring programmatic web interaction. Do NOT use for: tasks requiring no browser (pure API calls, static file manipulation, CLI-only scripting), when a simpler HTTP client suffices, or when the target resource is accessible via a direct API without rendering.
allowed-tools: Bash(npx agent-browser:*), Bash(agent-browser:*)
---

# Browser Automation with agent-browser

## Core Workflow

Every browser automation follows this pattern:

1. **Navigate**: `agent-browser open <url>`
2. **Snapshot**: `agent-browser snapshot -i` (get element refs like `@e1`, `@e2`)
3. **Interact**: Use refs to click, fill, select
4. **Re-snapshot**: After navigation or DOM changes, get fresh refs

```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
# Output: @e1 [input type="email"], @e2 [input type="password"], @e3 [button] "Submit"

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # Check result
```

## Input Validation

| Input | Required Format | Common Mistake |
|-------|----------------|----------------|
| URL | Must include protocol (`https://` or `file://`) | Bare domain `example.com` fails |
| Ref (`@eN`) | Must come from the **current** snapshot | Stale refs after navigation cause `Element not found` |
| CSS selector | Valid CSS selector string | Refs (`@eN`) do not accept CSS syntax interchangeably |
| Wait timeout | Integer milliseconds | Strings like `"5s"` are not accepted |
| Session name | Alphanumeric, no spaces | Spaces in session names cause daemon conflicts |
| JS via `eval` | Unquoted or `--stdin`/`-b` for complex expressions | Shell history expansion and nested quotes corrupt JS |

## Error Contract

| Exit Code | Meaning | Recovery |
|-----------|---------|----------|
| 0 | Success | — |
| 1 | Command error (invalid args, element not found, timeout) | Check stderr; re-snapshot if ref-related |
| 2 | Daemon error (browser crashed, connection lost) | Run `agent-browser close` then retry |

**Common error patterns:**
- `Element not found @eN` — ref is stale; re-snapshot and use new refs
- `Navigation timeout` — page is slow; add `wait --load networkidle` before interaction
- `Domain not allowed` — `AGENT_BROWSER_ALLOWED_DOMAINS` blocks the URL; update allowlist
- `Action denied by policy` — check `AGENT_BROWSER_ACTION_POLICY` config
- `Daemon not running` — run `agent-browser close` to reset, then retry

## Edge Cases

| Scenario | Issue | Fix |
|----------|-------|-----|
| Click navigates to new page | `@eN` refs invalidate on page change | Re-snapshot after every navigation |
| Dynamic content (modals, dropdowns) | DOM mutation invalidates current refs | Re-snapshot after each dynamic update |
| Slow or JS-heavy page | `open` returns before content is ready | Add `wait --load networkidle` after `open` |
| JS with nested quotes or multiline | Shell corrupts the expression | Use `eval --stdin <<'EVALEOF'` or `-b` (base64) |
| Leaked session from prior run | Stale daemon causes unexpected state | Run `agent-browser close` before starting new work |
| Chaining with output dependency | Cannot parse intermediate output in a chain | Run commands separately when output must be parsed |
| Concurrent agents | Default session is shared, causes conflicts | Always use `--session <name>` for each agent |
| File:// URLs | Blocked by default security policy | Pass `--allow-file-access` explicitly |

## Command Chaining

Commands can be chained with `&&` in a single shell invocation. The browser persists between commands via a background daemon, so chaining is safe and more efficient than separate calls.

```bash
agent-browser open https://example.com && agent-browser wait --load networkidle && agent-browser snapshot -i
agent-browser fill @e1 "user@example.com" && agent-browser fill @e2 "password123" && agent-browser click @e3
agent-browser open https://example.com && agent-browser wait --load networkidle && agent-browser screenshot page.png
```

**When to chain:** Use `&&` when you don't need to read the output of an intermediate command before proceeding. Run commands separately when you need to parse output first (e.g., snapshot to discover refs).

## Essential Commands

```bash
# Navigation
agent-browser open <url>              # Navigate (aliases: goto, navigate)
agent-browser close                   # Close browser

# Snapshot
agent-browser snapshot -i             # Interactive elements with refs (recommended)
agent-browser snapshot -i -C          # Include cursor-interactive elements
agent-browser snapshot -s "#selector" # Scope to CSS selector

# Interaction (use @refs from snapshot)
agent-browser click @e1               # Click element
agent-browser click @e1 --new-tab     # Click and open in new tab
agent-browser fill @e2 "text"         # Clear and type text
agent-browser type @e2 "text"         # Type without clearing
agent-browser select @e1 "option"     # Select dropdown option
agent-browser check @e1               # Check checkbox
agent-browser press Enter             # Press key
agent-browser keyboard type "text"    # Type at current focus
agent-browser keyboard inserttext "text"  # Insert without key events
agent-browser scroll down 500         # Scroll page
agent-browser scroll down 500 --selector "div.content"  # Scroll within container

# Get information
agent-browser get text @e1            # Get element text
agent-browser get url                 # Get current URL
agent-browser get title               # Get page title

# Wait
agent-browser wait @e1                # Wait for element
agent-browser wait --load networkidle # Wait for network idle
agent-browser wait --url "**/page"    # Wait for URL pattern
agent-browser wait 2000               # Wait milliseconds

# Downloads
agent-browser download @e1 ./file.pdf
agent-browser wait --download ./output.zip
agent-browser --download-path ./downloads open <url>

# Capture
agent-browser screenshot              # Screenshot to temp dir
agent-browser screenshot --full       # Full page screenshot
agent-browser screenshot --annotate   # Annotated with numbered labels
agent-browser pdf output.pdf

# Diff
agent-browser diff snapshot
agent-browser diff snapshot --baseline before.txt
agent-browser diff screenshot --baseline before.png
agent-browser diff url <url1> <url2>
```

## Common Patterns

### Form Submission

```bash
agent-browser open https://example.com/signup
agent-browser snapshot -i
agent-browser fill @e1 "Jane Doe"
agent-browser fill @e2 "jane@example.com"
agent-browser select @e3 "California"
agent-browser check @e4
agent-browser click @e5
agent-browser wait --load networkidle
```

### Authentication with Auth Vault (Recommended)

```bash
echo "pass" | agent-browser auth save github --url https://github.com/login --username user --password-stdin
agent-browser auth login github
agent-browser auth list
agent-browser auth show github
agent-browser auth delete github
```

### Session Persistence

```bash
agent-browser --session-name myapp open https://app.example.com/login
# ... login flow ...
agent-browser close  # State auto-saved

agent-browser --session-name myapp open https://app.example.com/dashboard

export AGENT_BROWSER_ENCRYPTION_KEY=$(openssl rand -hex 32)
agent-browser --session-name secure open https://app.example.com

agent-browser state list
agent-browser state clear myapp
agent-browser state clean --older-than 7
```

### Data Extraction

```bash
agent-browser open https://example.com/products
agent-browser snapshot -i
agent-browser get text @e5
agent-browser get text body > page.txt
agent-browser snapshot -i --json
```

### Parallel Sessions

```bash
agent-browser --session site1 open https://site-a.com
agent-browser --session site2 open https://site-b.com
agent-browser session list
```

## Security

All security features are opt-in. By default, agent-browser imposes no restrictions.

### Content Boundaries

```bash
export AGENT_BROWSER_CONTENT_BOUNDARIES=1
agent-browser snapshot
```

### Domain Allowlist

```bash
export AGENT_BROWSER_ALLOWED_DOMAINS="example.com,*.example.com"
```

### Action Policy

```bash
export AGENT_BROWSER_ACTION_POLICY=./policy.json
```

Example `policy.json`:
```json
{"default": "deny", "allow": ["navigate", "snapshot", "click", "scroll", "wait", "get"]}
```

### Output Limits

```bash
export AGENT_BROWSER_MAX_OUTPUT=50000
```

## Timeouts and Slow Pages

```bash
agent-browser wait --load networkidle
agent-browser wait "#content"
agent-browser wait @e1
agent-browser wait --url "**/dashboard"
agent-browser wait --fn "document.readyState === 'complete'"
agent-browser wait 5000
```

Override default 25s timeout: `AGENT_BROWSER_DEFAULT_TIMEOUT=60000`

## Annotated Screenshots (Vision Mode)

```bash
agent-browser screenshot --annotate
agent-browser click @e2
```

Use when: page has unlabeled icon buttons, canvas/chart elements, or you need spatial reasoning.

## Semantic Locators

```bash
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find role button click --name "Submit"
agent-browser find placeholder "Search" type "query"
agent-browser find testid "submit-btn" click
```

## JavaScript Evaluation

```bash
agent-browser eval 'document.title'

agent-browser eval --stdin <<'EVALEOF'
JSON.stringify(
  Array.from(document.querySelectorAll("img"))
    .filter(i => !i.alt)
    .map(i => ({ src: i.src.split("/").pop(), width: i.width }))
)
EVALEOF

agent-browser eval -b "$(echo -n 'Array.from(document.querySelectorAll("a")).map(a => a.href)' | base64)"
```

**Rules:** single-line no nested quotes → regular quotes; nested quotes/multiline → `--stdin`; programmatic → `-b`.

## Configuration File

```json
{
  "headed": true,
  "proxy": "http://localhost:8080",
  "profile": "./browser-data"
}
```

Priority: `~/.agent-browser/config.json` < `./agent-browser.json` < env vars < CLI flags.

## Deep-Dive Documentation

| Reference | When to Use |
|-----------|-------------|
| [references/commands.md](references/commands.md) | Full command reference |
| [references/snapshot-refs.md](references/snapshot-refs.md) | Ref lifecycle and troubleshooting |
| [references/session-management.md](references/session-management.md) | Parallel sessions, state persistence |
| [references/authentication.md](references/authentication.md) | Login flows, OAuth, 2FA |
| [references/video-recording.md](references/video-recording.md) | Recording for debugging |
| [references/profiling.md](references/profiling.md) | Chrome DevTools profiling |
| [references/proxy-support.md](references/proxy-support.md) | Proxy configuration |

## Experimental: Native Mode

```bash
agent-browser --native open example.com
export AGENT_BROWSER_NATIVE=1
```

Supports Chromium and Safari via CDP. Firefox/WebKit not yet supported. Run `agent-browser close` before switching modes.

## Ready-to-Use Templates

| Template | Description |
|----------|-------------|
| [templates/form-automation.sh](templates/form-automation.sh) | Form filling with validation |
| [templates/authenticated-session.sh](templates/authenticated-session.sh) | Login once, reuse state |
| [templates/capture-workflow.sh](templates/capture-workflow.sh) | Content extraction with screenshots |