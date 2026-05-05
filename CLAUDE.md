# Digital Clone (brunof)

Read AGENTS.md for full project context.
Read STATUS.md for current state and recent changes.

## IMPORTANT: After making any changes, update STATUS.md with what you did (date + one-line summary in "Recent Changes" section, update "Last Updated By").

## Quick Reference
- Bot personality: "brunofernandes" — direct, witty, Abdurakhmon's alter ego
- Stack: Python + Groq (Llama 3.3 70B) + ChromaDB + pyTelegramBotAPI + Gemini (voice)
- Group privacy: only GROUP_IDENTITY + GROUP_SAFE_PAGES exposed. Never leak private info.
- Auto-update: daily at 6 AM via auto_update.py (digest + inbox + clean)
- Owner: Abdurakhmon (Telegram ID 1946444733)
- Run with: `python telegram-bot.py`
