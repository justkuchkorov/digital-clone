# Project Status — brunof (digital-clone)

> This file is the handoff log between tools (Claude Code, Codex, etc.)
> Each tool updates this after making changes so the next session knows what happened.

## Current State
- **Active version**: Python bot is live for Telegram; OpenClaw is configured but not active on Telegram
- **LLM**: Groq free tier (Llama 3.3 70B) with MODEL_CHAIN fallback
- **Running**: Python bot manually via `C:\Program Files\KiCad\9.0\bin\python.exe telegram-bot.py`; OpenClaw can be started via `powershell -ExecutionPolicy Bypass -File .\run_openclaw.ps1`
- **Auto-update**: Windows Task Scheduler, daily 6 AM
- **GitHub**: https://github.com/justkuchkorov/digital-clone (pushed 2026-05-05)

## Recent Changes
- 2026-05-05: Added live semantic conversation memory; meaningful owner DMs are now embedded into Chroma conversations right after replies
- 2026-05-05: Fixed brunof memory self-answer; bot now says it has persistent chat/wiki/deep memory and saves more life-update phrases immediately
- 2026-05-05: Added owner-only live Google bridge to Python brunof using gogcli; Gmail/calendar questions now inject fresh data into replies
- 2026-05-05: Stopped OpenClaw Gateway and restored Python Telegram bot after OpenClaw failed to reply due to oversized context/Groq limits
- 2026-05-05: Revisited OpenClaw; installed CLI 2026.5.3-1, connected Telegram, locked DMs to owner ID, stopped Python bot to avoid 409 conflicts
- 2026-05-05: Installed local gogcli v0.12.0, completed Google OAuth for abdurakhmonkuchkorov@gmail.com, verified Calendar read and Gmail search
- 2026-05-05: Added `run_openclaw.ps1`; OpenClaw main agent limited to `gog` skill to reduce Groq prompt size
- 2026-05-05: Added owner-only live Chroma deep-memory retrieval for DMs; seeded profile/wiki vectors (9 profile chunks, 102 wiki chunks)
- 2026-05-05: Added local `.vendor` dependency bootstrap, missing RAG config, custom Gemini embedding wrapper, and wiki ingestion path
- 2026-05-05: Pushed to GitHub with README, AGENTS.md, CLAUDE.md
- 2026-05-05: GitHub cleanup complete (profile README, weak repos archived)
- 2026-05-04: Group chat privacy, auto-update engine, roast level fix
- 2026-05-04: OpenClaw migration attempted but unstable — Python bot stays as primary

## Known Issues
- Llama personality is weak (doesn't hold character consistently)
- `learned.md` cleanup is still trigger/digest-based, but semantic conversation retrieval now updates live
- OpenClaw natural-language `gog` use still fails validation in local smoke tests (`attempted to call tool 'gog' which was not in request.tools`); direct gog CLI works and native skill command path should be tested in Telegram
- OpenClaw prompts/context are too large for Groq free tier during Telegram use; caused no reply / timeout
- OpenClaw Gateway is not installed as a Scheduled Task/service
- Voice responses slow (Gemini transcription)
- Live Google bridge is read-only for now; sending emails / creating calendar events still needs explicit implementation and confirmation flow

## Planned Next
- [ ] Swap to GPT-4o-mini as primary LLM (keep Groq as fallback) — user will say when
- [ ] Better personality holding
- [ ] Fix/verify OpenClaw natural-language gog tool routing
- [ ] Install OpenClaw Gateway as service once stable

## Last Updated By
Codex — 2026-05-05
