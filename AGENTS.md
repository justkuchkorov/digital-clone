# Digital Clone (brunof) — Project Context

> **IMPORTANT**: Read STATUS.md for current state and recent changes.
> **IMPORTANT**: After making any changes, update STATUS.md with what you did (date + one-line summary in "Recent Changes", update "Last Updated By").

## What This Is
Personal AI second brain living in Telegram. Responds as "brunofernandes" (brunof for short) — Abdurakhmon's digital alter ego. Knows him through ingested personal data (chat exports, docs, notes) and responds with his communication style.

## Owner
Abdurakhmon Kuchkorov — EE student finishing BSc at University of Debrecen, Hungary. Uzbek. Into industrial automation, AI, football. Direct communication style, no buzzwords.

## Architecture
- `telegram-bot.py` — Telegram handlers (text, voice, groups, /digest command)
- `brain.py` — LLM agent with RAG, system prompt, group/DM modes. MODEL_CHAIN fallback: llama-3.3-70b → llama-4-scout → llama-3.1-8b
- `memory.py` — ChromaDB vector store for retrieval
- `ingest.py` — CLI to load personal data into vector DB
- `auto_update.py` — Daily digest: chat logs → facts, inbox → wiki, dedup. Runs via Windows Task Scheduler at 6 AM.
- `wiki/` — Personal knowledge base (markdown pages). Core pages: identity.md, education.md, projects.md, struggles.md, preferences.md
- `data/` — Raw data, chat exports, inbox folder (gitignored)

## Key Design Decisions
- **Group chat privacy**: Groups get stripped context (GROUP_IDENTITY + GROUP_SAFE_PAGES only). Private keywords (salary, interview, struggles) filtered from learned.md in groups.
- **Bot responds in groups only when @mentioned or replied to**
- **Auto-update engine**: 3 systems — DIGEST (chat logs → LLM → facts), INBOX (file drop → compile wiki), SELF-CLEAN (dedup learned.md)
- **Groq free tier**: 100K TPD per model, MODEL_CHAIN fallback handles rate limits
- **OWNER_ID**: 1946444733 (only owner can run /digest)

## Current Limitations
- Llama on Groq is the personality bottleneck — doesn't hold character well
- OpenClaw migration was attempted but unstable; Python bot is the active version
- Voice via Gemini works but is slow

## Style Rules for the Bot
- Never say "bro" in every sentence (1-2 max per message)
- 1-2 emojis max per message
- Answer what was actually asked, don't ramble
- Be chill, witty, helpful. Roast only when the moment is right.
- In DMs: full personality + knowledge. In groups: minimal, privacy-safe.

## Dev Preferences
- Direct, no boilerplate explanations
- Agent does all legwork — never ask user to browse/paste/search
- Test changes by running the bot and sending messages
