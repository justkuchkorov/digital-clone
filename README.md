# Digital Clone (brunof)

AI-powered personal second brain that lives in Telegram. Knows me through ingested personal data (chat exports, documents, notes) and responds with my communication style. Works in DMs and group chats with privacy protection.

## What It Does

- Answers questions about me using RAG over a personal knowledge wiki
- Maintains conversation context (20-message rolling history)
- Handles voice messages (transcription via Gemini)
- Group chat mode — responds only when @mentioned, protects private info
- Auto-updates its knowledge base daily from new conversations and file drops

## Architecture

```
digital-clone/
├── telegram-bot.py      Telegram handlers (text, voice, groups, commands)
├── brain.py             LLM agent with RAG, personality system prompt, group/DM modes
├── memory.py            ChromaDB vector store + retrieval
├── ingest.py            CLI to load personal data into vector DB
├── auto_update.py       Daily digest: chat logs → facts, inbox → wiki, dedup
├── config.py            API keys, model config, paths
├── compile_wiki.py      Compiles raw data into structured wiki pages
├── wiki/                Personal knowledge base (markdown pages)
└── data/                Raw data, chat exports, inbox (gitignored)
```

## Stack

| Component | Choice |
|-----------|--------|
| LLM | Groq (Llama 3.3 70B) |
| Embeddings + Voice | Gemini |
| Vector DB | ChromaDB (local) |
| Bot framework | pyTelegramBotAPI |
| Auto-update | Windows Task Scheduler + custom digest engine |

## Setup

```bash
pip install -r requirements.txt
```

`.env`:
```
TELEGRAM_BOT_TOKEN=your_token
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
```

Run:
```bash
python telegram-bot.py
```

## Privacy

- Group chats get a stripped-down context (no private info)
- Sensitive keywords (salary, interviews, personal struggles) are filtered from group mode
- Full knowledge only accessible in private DMs with the owner

## Credits

Built by Abdurakhmon Kuchkorov ([@justkuchkorov](https://t.me/justkuchkorov))
