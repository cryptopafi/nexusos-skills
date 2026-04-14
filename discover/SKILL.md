---
name: discover
description: "Query what the other user (Pafi or Leo) has been building recently, and show the full shared toolkit. Use when user says '/discover', 'what has Leo built', 'what has Pafi built', 'show me the whiteboard', 'what tools do we have', 'ce a construit Leo', 'ce a construit Pafi', 'show toolkit'. Do NOT invoke for: Cortex search requests (use cortex-search), general questions about the system, or when the user wants to build something new."
argument-hint: "[pafi|leo|toolkit|all]"
---

# /discover — Cross-User Discovery + Shared Toolkit

Show what the other user has been building and display the full shared toolkit.

Arguments: $ARGUMENTS

## Execution

### Step 1: Detect Users
- Read `memory/users/_active-user.md` to identify current user
- Set `other_user` = the opposite (Pafi<>Leo)
- If argument is "pafi" or "leo", override other_user to show that specific user's work
- If argument is "toolkit", skip to Step 4

### Step 2: Other User's Recent Work (Notion)
Query Team Dashboard Notion DB (ID: `335d31d1-1b7d-8109-ab38-000bbd0ed2cf`):
- Filter: Owner = other_user
- Sort: Last Updated descending
- Limit: 10

Display as:
```
## What {other_user} has been building

| Name | Type | Status | Invocation |
|------|------|--------|------------|
| ... | ... | ... | ... |
```

Mark any items where `UnreadBy{current_user}` = true with "NEW" badge.
After displaying, clear the unread checkbox for current user only.

### Step 3: Other User's Recent Sessions (Cortex)
Query Cortex `sessions` collection filtered by other_user metadata, limit 5:
```
cortex_search(query="session {other_user}", collection="sessions", limit=5)
```

Display brief summary of each session (date, accomplishments).

### Step 4: Common Toolkit (full whiteboard)
Query Team Dashboard Notion DB:
- Filter: Status = Ready
- Sort: Type ascending, then Name ascending

Display grouped by type:
```
## Common Toolkit — Ready to Use

### Agents
| Name | Owner | Invocation | Description |
...

### Procedures
| Name | Owner | Invocation | Description |
...

### Skills
| Name | Owner | Invocation | Description |
...

### Plugins & Tools
| Name | Owner | Invocation | Description |
...
```

### Step 5: Summary
- Count total items by type
- Note any items with Status = Building (work in progress)
- If any UnreadBy{current_user} = true, highlight them as NEW
