---
name: briefed
description: Set up and run a personal AI newsletter intelligence system called Briefed. Fetches Gmail newsletters daily, uses Claude Haiku to extract article summaries, and serves a polished local web reader app with voting, notes, and interest tracking. Use when a user asks to set up a newsletter reader, daily digest, inbox intelligence tool, or newsletter summariser with OpenClaw.
---

# Briefed

A daily newsletter digest pipeline + local web reader. Gmail → Haiku summaries → web app → notification ping.

## Architecture

```
[Gmail]
   ↓  pre-fetch.py (fetches, filters, extracts compact metadata)
[newsletter-inbox.json]
   ↓  Haiku cron agent (reads compact JSON, writes AI summaries)
[newsletter-today.json]
   ↓  fetch-bodies.py (adds full HTML email bodies)
[newsletter-today.json + bodies]
   ↓  Express web reader (default port 3001)
[Notification ping → user opens reader]
```

**Why split fetch/summarise?** Raw Gmail API JSON overflows Haiku's context. Python handles data wrangling; Haiku handles cognition.

## Prerequisites

- `gog` (gogcli) installed and authenticated — Gmail read-only OAuth
- Node.js ≥18 (for the reader web app)
- `claude-haiku-4-5` on the OpenClaw models allowlist
- A notification channel configured in OpenClaw (Telegram, Discord, etc.)

## Setup

### 1. Install Gmail OAuth

```bash
# Install gogcli if not present
brew install gogcli   # or: npm install -g gogcli

# Authenticate (needs GCP OAuth client JSON — download from Google Cloud Console)
gog auth login --account YOUR@EMAIL.COM --credentials ~/client_secret_*.json
```

### 2. Deploy the reader app

```bash
# Copy the reader to the workspace
cp -r assets/reader/ ~/.openclaw/workspace/briefed/
cd ~/.openclaw/workspace/briefed
npm install
```

### 3. Set your Gmail account

Set the `NEWSLETTER_ACCOUNT` environment variable, or edit `ACCOUNT` directly in both scripts:

```bash
# scripts/pre-fetch.py  — line ~14
# scripts/fetch-bodies.py — line ~12
ACCOUNT = os.environ.get('NEWSLETTER_ACCOUNT', 'your@gmail.com')
```

The easiest approach is to set it in the LaunchAgent plist (see Step 5).

### 4. Configure interests

Create `~/.openclaw/workspace/newsletter-interests.json` (or let it be auto-created on first run):

```json
{
  "version": 1,
  "topics": { "ai": 0.9, "startups": 0.8, "design": 0.75 },
  "signals": [],
  "sources": {}
}
```

### 5. Start the reader (macOS LaunchAgent for auto-start)

```bash
# Quick test
node ~/.openclaw/workspace/briefed/server.js

# Persistent — create ~/Library/LaunchAgents/ai.openclaw.briefed.plist
```

LaunchAgent plist template:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>ai.openclaw.briefed</string>
  <key>ProgramArguments</key><array>
    <string>/usr/local/bin/node</string>
    <string>/Users/YOUR_USER/.openclaw/workspace/briefed/server.js</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>NEWSLETTER_ACCOUNT</key><string>YOUR@EMAIL.COM</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>WorkingDirectory</key><string>/Users/YOUR_USER/.openclaw/workspace/briefed</string>
  <key>StandardOutPath</key><string>/tmp/briefed.log</string>
  <key>StandardErrorPath</key><string>/tmp/briefed.log</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/ai.openclaw.briefed.plist
```

### 6. Create the daily cron job

Use the OpenClaw cron tool with this agent prompt (fill in the placeholders):

```
Run my daily newsletter digest. Follow these steps exactly:

## Step 1 — Pre-fetch emails
Run: NEWSLETTER_ACCOUNT=YOUR@EMAIL.COM python3 ~/.openclaw/workspace/briefed/scripts/pre-fetch.py

## Step 2 — Read the compact inbox
Read: ~/.openclaw/workspace/newsletter-inbox.json

## Step 3 — Write newsletter-today.json with AI summaries
For each newsletter, write to ~/.openclaw/workspace/newsletter-today.json.
Use the snippet field to write real summaries — do NOT just repeat the subject line.
Score by interest: (adjust topics and weights to match your interests)
  ai/ml=0.9, startups=0.85, design=0.8, finance=0.75, general=0.6

Schema per story:
{ "id", "rank", "source", "subject", "headline", "summary", "bullets": [], "threadId", "gmailUrl", "score", "body": "" }

## Step 4 — Fetch HTML bodies
Run: NEWSLETTER_ACCOUNT=YOUR@EMAIL.COM python3 ~/.openclaw/workspace/briefed/scripts/fetch-bodies.py

## Step 5 — Send notification
Send (via your configured channel):
"📬 Today's digest is ready — <N> stories waiting.\n→ http://YOUR_HOST:3001"

## Step 6 — Final reply
📬 *Briefed — [DD Mon YYYY]* · <N> stories
*<rank>. <Source>* — <Headline>
<One sentence summary>
(repeat for all stories)
_Open the reader → http://YOUR_HOST:3001_
```

Cron schedule: `0 7 * * *` (7am daily), model: `anthropic/claude-haiku-4-5`, delivery: `announce`.

## Data Files

All data files live in `~/.openclaw/workspace/`:

| File | Purpose |
|------|---------|
| `newsletter-inbox.json` | Compact pre-fetched email metadata (ephemeral) |
| `newsletter-today.json` | Today's stories with summaries + HTML bodies |
| `newsletter-interests.json` | Topic weights + vote/open signals |
| `newsletter-notes.json` | Per-story user notes |
| `reading-list.md` | Saved/bookmarked stories |

## Reader API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/today` | GET | All stories (bodies stripped) |
| `/api/story/:id` | GET | Single story with full HTML body |
| `/api/vote` | POST | `{ storyId, vote: "up"\|"down"\|"open" }` |
| `/api/save` | POST | `{ storyId }` — adds to reading-list.md |
| `/api/note` | POST | `{ storyId, note }` |
| `/api/notes` | GET | All notes |

## Filtering Transactional Email

`scripts/pre-fetch.py` has two tunable lists near the top:
- `SKIP_SUBJECT_PATTERNS` — subject substrings that flag an email as transactional
- `SKIP_SENDERS` — sender names that are always transactional (e.g. banks, shops)

Tune these when transactional emails slip through.

## Branding

The reader shows "Briefed" with a blue "B" logo by default. To customise, edit `public/index.html` and `public/icon.svg`.
