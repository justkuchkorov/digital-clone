"""
Auto-Update Engine for Brunof's brain.

Three systems:
1. DIGEST — reads brunof's chat logs, extracts new facts via LLM, updates learned.md
2. INBOX — watches data/inbox/ for new files, auto-compiles into wiki pages
3. SELF-CLEAN — deduplicates and cleans learned.md via LLM

Run modes:
  python auto_update.py              # run all once
  python auto_update.py --loop       # run every 6 hours
  python auto_update.py --digest     # only digest chat logs
  python auto_update.py --inbox      # only process inbox
  python auto_update.py --clean      # only clean learned.md
"""

import json
import sys
import os
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

_vendor_dir = Path(__file__).resolve().parent / ".vendor"
if sys.version_info[:2] == (3, 11) and _vendor_dir.exists() and str(_vendor_dir) not in sys.path:
    sys.path.insert(0, str(_vendor_dir))

from groq import Groq
from config import GROQ_API_KEY, WIKI_DIR, DATA_DIR

sys.stdout.reconfigure(encoding="utf-8")

client = Groq(api_key=GROQ_API_KEY)

# Model chain — same as brain.py
MODEL_CHAIN = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]

CHAT_LOG_DIR = Path(DATA_DIR) / "chat_logs"
INBOX_DIR = Path(DATA_DIR) / "inbox"
INBOX_DONE_DIR = INBOX_DIR / "processed"
STATE_FILE = Path(DATA_DIR) / "auto_update_state.json"
WIKI_PATH = Path(WIKI_DIR)
LEARNED_PATH = WIKI_PATH / "learned.md"


def _llm(prompt: str, max_tokens: int = 2000) -> str:
    """Call LLM with model fallback."""
    for model in MODEL_CHAIN:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_tokens,
            )
            print(f"    [model: {model}]", flush=True)
            return resp.choices[0].message.content
        except Exception as e:
            if "429" in str(e) or "413" in str(e):
                print(f"    [{model}] rate limited, next...", flush=True)
                continue
            raise
    raise RuntimeError("All models exhausted")


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_digest_ts": "2000-01-01 00:00:00", "processed_inbox": []}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ============================================================
# 1. DIGEST — extract facts from chat logs
# ============================================================

def digest_chat_logs():
    """Read chat logs since last digest, extract new facts via LLM."""
    print("\n=== DIGEST: Processing chat logs ===", flush=True)
    state = _load_state()
    last_ts = state.get("last_digest_ts", "2000-01-01 00:00:00")

    # Collect new messages from ALL chat log files
    new_messages = []
    for log_file in sorted(CHAT_LOG_DIR.glob("*.jsonl")):
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts", "") > last_ts:
                    entry["_source"] = log_file.stem  # e.g. user_1946444733
                    new_messages.append(entry)
            except (json.JSONDecodeError, KeyError):
                continue

    if not new_messages:
        print("  No new messages since last digest.", flush=True)
        return

    print(f"  Found {len(new_messages)} new messages since {last_ts}", flush=True)

    # Group into conversation blocks (max ~50 messages to fit context)
    # Take the most recent ones if too many
    if len(new_messages) > 80:
        new_messages = new_messages[-80:]

    # Build conversation text
    convo_text = ""
    for msg in new_messages:
        role = "Abdurakhmon" if msg["role"] == "user" else "brunof"
        convo_text += f"[{msg.get('ts', '?')}] {role}: {msg['text']}\n"

    # Truncate if too long
    if len(convo_text) > 6000:
        convo_text = convo_text[-6000:]

    # Load existing learned.md
    existing_learned = ""
    if LEARNED_PATH.exists():
        existing_learned = LEARNED_PATH.read_text(encoding="utf-8")

    prompt = f"""You are analyzing recent conversations between Abdurakhmon and his AI clone "brunof".
Your job is to extract NEW facts, preferences, and life updates that brunof should remember.

ALREADY KNOWN (don't repeat these):
{existing_learned}

NEW CONVERSATIONS:
{convo_text}

Extract ONLY genuinely new information. For each fact, write ONE clean line in this format:
- [YYYY-MM-DD] <clear, distilled fact>

Categories to look for:
1. Personal facts: new info about his life, plans, relationships, events
2. Behavior rules: how he wants brunof to respond (tone, emoji, language)
3. Life updates: job progress, thesis, projects, decisions made
4. Preferences: things he likes/dislikes, opinions expressed
5. People: new people mentioned, relationships clarified

Rules:
- SKIP raw chat messages, jokes, greetings, and filler
- SKIP anything already in the ALREADY KNOWN section
- SKIP vague statements — only save concrete, actionable facts
- Distill each entry into a clean fact, don't copy raw messages
- Use today's date: {datetime.now().strftime("%Y-%m-%d")}
- If nothing genuinely new was learned, respond with exactly: NOTHING_NEW

Output ONLY the bullet points (or NOTHING_NEW). No headers, no explanations."""

    print("  Asking LLM to extract facts...", flush=True)
    result = _llm(prompt, max_tokens=1000)

    if "NOTHING_NEW" in result.strip():
        print("  No new facts found.", flush=True)
    else:
        # Append new facts to learned.md
        new_lines = [l.strip() for l in result.strip().splitlines() if l.strip().startswith("-")]
        if new_lines:
            with open(LEARNED_PATH, "a", encoding="utf-8") as f:
                for line in new_lines:
                    f.write(line + "\n")
            print(f"  Added {len(new_lines)} new facts to learned.md", flush=True)
            for line in new_lines:
                print(f"    {line}", flush=True)
        else:
            print("  LLM returned no valid facts.", flush=True)

    # Update state
    latest_ts = max(m.get("ts", "") for m in new_messages)
    state["last_digest_ts"] = latest_ts
    _save_state(state)
    print(f"  Digest complete. Next digest starts from: {latest_ts}", flush=True)


# ============================================================
# 2. INBOX — auto-compile dropped files into wiki
# ============================================================

def process_inbox():
    """Watch data/inbox/ for new files and compile them into wiki pages."""
    print("\n=== INBOX: Checking for new files ===", flush=True)

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DONE_DIR.mkdir(parents=True, exist_ok=True)

    state = _load_state()
    processed = set(state.get("processed_inbox", []))

    files = [f for f in INBOX_DIR.iterdir()
             if f.is_file() and f.name not in processed and f.suffix in (
                 ".txt", ".md", ".json", ".html", ".csv")]

    if not files:
        print("  No new files in inbox.", flush=True)
        return

    for filepath in files:
        print(f"\n  Processing: {filepath.name}", flush=True)

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"    Error reading: {e}", flush=True)
            continue

        # Truncate large files
        if len(content) > 10000:
            content = content[:10000] + "\n... [truncated]"

        # Determine a slug for the wiki page
        slug = filepath.stem.lower().replace(" ", "-").replace("_", "-")
        wiki_file = WIKI_PATH / f"{slug}.md"

        # Skip if wiki page already exists
        if wiki_file.exists():
            print(f"    Wiki page {wiki_file.name} already exists, skipping.", flush=True)
            processed.add(filepath.name)
            continue

        prompt = f"""You are building a personal wiki about Abdurakhmon (abdi).
You have a new data file to analyze and compile into a wiki article.

FILE: {filepath.name}
CONTENT:
{content}

Write a structured wiki article about what this data reveals about Abdurakhmon.
Focus on: personal facts, relationships, interests, plans, personality, opinions.

Rules:
- Write in markdown format
- Be specific — use actual data from the file
- 300-600 words
- Title should describe the content source
- Only include information about Abdurakhmon, skip irrelevant data"""

        try:
            article = _llm(prompt)
            wiki_file.write_text(f"# {filepath.stem}\n\n{article}", encoding="utf-8")
            print(f"    Compiled → {wiki_file.name}", flush=True)

            # Move to processed
            shutil.move(str(filepath), str(INBOX_DONE_DIR / filepath.name))
            processed.add(filepath.name)

        except Exception as e:
            print(f"    Error compiling: {e}", flush=True)

    state["processed_inbox"] = list(processed)
    _save_state(state)

    # Rebuild index
    _rebuild_index()


# ============================================================
# 3. SELF-CLEAN — deduplicate and distill learned.md
# ============================================================

def clean_learned():
    """Use LLM to deduplicate and clean learned.md."""
    print("\n=== CLEAN: Tidying up learned.md ===", flush=True)

    if not LEARNED_PATH.exists():
        print("  No learned.md to clean.", flush=True)
        return

    current = LEARNED_PATH.read_text(encoding="utf-8")
    lines = [l for l in current.splitlines() if l.strip()]

    if len(lines) < 5:
        print("  Too few entries to clean.", flush=True)
        return

    prompt = f"""You are cleaning up a memory file for an AI assistant called brunof.
This file contains facts and rules learned from conversations with Abdurakhmon.

CURRENT CONTENTS:
{current}

Your job:
1. REMOVE duplicates (keep the better-worded one)
2. MERGE related entries into single clear entries
3. REMOVE entries that are vague, useless, or just raw chat messages
4. KEEP all genuinely useful facts, preferences, and behavior rules
5. KEEP the date tags [YYYY-MM-DD] on each entry
6. Sort by category: behavior rules first, then personal facts, then people info

Output the cleaned file in this exact format:
# Learned from Conversations
- [date] fact here
- [date] fact here
...

Output ONLY the cleaned file content. No explanations."""

    print("  Asking LLM to clean and deduplicate...", flush=True)
    result = _llm(prompt, max_tokens=1500)

    # Validate — must start with # and have bullet points
    if result.strip().startswith("#") and "- [" in result:
        # Backup old version
        backup = LEARNED_PATH.with_suffix(".md.bak")
        shutil.copy2(LEARNED_PATH, backup)
        LEARNED_PATH.write_text(result.strip() + "\n", encoding="utf-8")

        old_count = len([l for l in current.splitlines() if l.strip().startswith("-")])
        new_count = len([l for l in result.splitlines() if l.strip().startswith("-")])
        print(f"  Cleaned: {old_count} entries → {new_count} entries", flush=True)
        print(f"  Backup saved to: {backup.name}", flush=True)
    else:
        print("  LLM output didn't pass validation, skipping.", flush=True)


# ============================================================
# UTILS
# ============================================================

def _rebuild_index():
    """Rebuild wiki/index.md with all current pages."""
    core = ["identity.md", "education.md", "projects.md", "struggles.md", "preferences.md"]
    all_pages = sorted(WIKI_PATH.glob("*.md"))

    lines = ["# Wiki Index — Abdurakhmon's Digital Brain\n"]

    lines.append("## Core Profile")
    for name in core:
        fp = WIKI_PATH / name
        if fp.exists():
            lines.append(f"- [[{fp.stem}]]")

    lines.append("\n## All Pages")
    for f in all_pages:
        if f.name in ("index.md", "learned.md") or f.name in core:
            continue
        size = f.stat().st_size
        lines.append(f"- [[{f.stem}]] ({size:,} bytes)")

    lines.append(f"\n## Learned Facts")
    lines.append(f"- [[learned]] — auto-updated from conversations")

    (WIKI_PATH / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print("  Index rebuilt.", flush=True)


# ============================================================
# MAIN
# ============================================================

def run_all():
    """Run all auto-update systems."""
    print(f"\n{'='*50}", flush=True)
    print(f"  BRUNOF AUTO-UPDATE — {datetime.now().strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"{'='*50}", flush=True)

    digest_chat_logs()
    process_inbox()
    clean_learned()

    print(f"\n{'='*50}", flush=True)
    print(f"  AUTO-UPDATE COMPLETE", flush=True)
    print(f"{'='*50}\n", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Brunof Auto-Update Engine")
    parser.add_argument("--loop", action="store_true", help="Run every 6 hours")
    parser.add_argument("--digest", action="store_true", help="Only digest chat logs")
    parser.add_argument("--inbox", action="store_true", help="Only process inbox")
    parser.add_argument("--clean", action="store_true", help="Only clean learned.md")
    parser.add_argument("--interval", type=int, default=6, help="Loop interval in hours (default: 6)")
    args = parser.parse_args()

    if args.digest:
        digest_chat_logs()
    elif args.inbox:
        process_inbox()
    elif args.clean:
        clean_learned()
    elif args.loop:
        print(f"Running auto-update every {args.interval} hours. Ctrl+C to stop.", flush=True)
        while True:
            try:
                run_all()
                print(f"Next run at: {datetime.now().strftime('%H:%M')} + {args.interval}h\n", flush=True)
                time.sleep(args.interval * 3600)
            except KeyboardInterrupt:
                print("\nStopped.", flush=True)
                break
            except Exception as e:
                print(f"\n[ERROR] {e}", flush=True)
                print(f"Retrying in 30 min...", flush=True)
                time.sleep(1800)
    else:
        run_all()


if __name__ == "__main__":
    main()
