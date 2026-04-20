---
name: buffer-publish
description: "Publish content to social media via Buffer API (LinkedIn, Instagram, Facebook, Twitter/X)"
---

Publish content to social media via Buffer API (LinkedIn, Instagram, Facebook, Twitter/X)

# Skill: Buffer Publish

## Auth

- Read token from Keychain:
  - `security find-generic-password -s "buffer" -a "access-token" -w`
- If missing:
  - `security add-generic-password -s "buffer" -a "access-token" -w "YOUR_TOKEN" -U`

## API

- Base URL: `https://api.bufferapp.com/1/`
- Rate limit target: keep under `60 req/min`

## Platform Prefix Mapping

- LinkedIn: `li_`
- Instagram: `ins_`
- Facebook: `fb_`
- Twitter/X: `tw_`

## Local Script

- Script path: `/Users/pafi/.claude/projects/-User
