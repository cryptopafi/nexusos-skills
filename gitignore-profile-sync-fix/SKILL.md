---
name: gitignore-profile-sync-fix
description: Use when profile YAML files silently excluded by gitignore causing cross-machine sync gaps
---

# Problema

Profile YAML files (*.local.md) in a plugin are silently gitignored by a broad glob pattern, so newly created profiles never sync across machines. Discovered when AUDIT-PRO's nexusos.local.md profile went missing between 2026-03-28 creation and 2026-04-20 — only pitch-deck.local.md was whitelisted in the plugin's .gitignore.

# Procedura

1. Check plugin's .gitignore for patterns like `profiles/*.local.md` that exclude profile files from git tracking.
2. Identify which profiles are canonical (ship with plugin) vs which are machine-specific (user overrides).
3. Whitelist canonical profiles explicitly with `!profiles/{name}.local.md` on their own line after the exclusion pattern.
4. After editing .gitignore, run `git add profiles/{name}.local.md` to force-track previously ignored file.
5. Commit both .gitignore and the profile together: `git commit -m "Whitelist canonical profile X"`.
6. Verify with `git ls-files profiles/` — all canonical profiles should appear.
7. Alternative naming: use `*.user.md` suffix for machine-specific profiles that should NOT sync, keep `*.local.md` for canonical/shared ones.

# Enforcement Loop

- WHERE: Run whenever a new canonical profile file is created in any plugin directory.
- WHEN: Immediately after file creation, before next sync-memory.sh run.
- HOW: `git check-ignore path/to/profile.local.md` should return exit 1 (not ignored). If it returns exit 0, whitelist is missing.
- CONNECT: Applies to all plugins with `*.local.md` or similar gitignore patterns. Reference case: AUDIT-PRO nexusos.local.md (2026-04-20).
- VERIFY: After commit, `git ls-files` shows the profile; on another machine, `git pull` delivers it.
