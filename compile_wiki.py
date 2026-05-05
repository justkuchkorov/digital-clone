"""
Wiki Compiler — Karpathy-style knowledge base builder.
Reads raw Telegram chat exports and compiles structured wiki articles about Abdurakhmon.
"""
import json
import sys
import os
from pathlib import Path
from groq import Groq
from config import GROQ_API_KEY, DATA_DIR, WIKI_DIR

sys.stdout.reconfigure(encoding="utf-8")

client = Groq(api_key=GROQ_API_KEY)
COMPILER_MODEL = "llama-3.3-70b-versatile"


def extract_my_messages(data: dict, my_name: str = "Abdurakhmon") -> list[dict]:
    """Extract messages from a single chat export."""
    messages = []

    # Single chat format (individual exports)
    if "messages" in data and "chats" not in data:
        chat_name = data.get("name", "Unknown")
        for msg in data.get("messages", []):
            text = msg.get("text", "")
            if isinstance(text, list):
                text = " ".join(
                    p if isinstance(p, str) else p.get("text", "")
                    for p in text
                )
            if text.strip() and len(text.strip()) > 5:
                messages.append({
                    "text": text.strip(),
                    "from": msg.get("from", ""),
                    "date": msg.get("date", ""),
                    "chat": chat_name,
                })

    # Full TG export format (chats.list)
    elif "chats" in data:
        for chat in data["chats"].get("list", []):
            chat_name = chat.get("name", "Unknown")
            chat_type = chat.get("type", "")
            # Skip public channels — not personal data
            if chat_type == "public_channel":
                continue
            for msg in chat.get("messages", []):
                text = msg.get("text", "")
                if isinstance(text, list):
                    text = " ".join(
                        p if isinstance(p, str) else p.get("text", "")
                        for p in text
                    )
                if text.strip() and len(text.strip()) > 5:
                    messages.append({
                        "text": text.strip(),
                        "from": msg.get("from", ""),
                        "date": msg.get("date", ""),
                        "chat": chat_name,
                    })

    return messages


def sample_messages(messages: list[dict], max_msgs: int = 300) -> list[dict]:
    """Sample messages evenly across the timeline."""
    if len(messages) <= max_msgs:
        return messages
    step = len(messages) // max_msgs
    return messages[::step][:max_msgs]


def compile_chat_to_wiki(chat_name: str, messages: list[dict], my_name: str = "Abdurakhmon") -> str:
    """Use LLM to compile chat messages into a wiki article."""
    # Separate my messages vs others
    my_msgs = [m for m in messages if m.get("from") == my_name]
    other_msgs = [m for m in messages if m.get("from") != my_name]

    # Sample to fit context window (Groq free tier: 12K TPM)
    sampled_my = sample_messages(my_msgs, 80)
    sampled_other = sample_messages(other_msgs, 40)

    # Build message block
    msg_block = ""
    for m in sampled_my:
        msg_block += f"[{m['date']}] {my_name}: {m['text']}\n"
    msg_block += "\n--- OTHER PERSON'S MESSAGES (for context) ---\n"
    for m in sampled_other:
        msg_block += f"[{m['date']}] {m['from']}: {m['text']}\n"

    # Truncate if too long (Groq context limit ~8K for output)
    if len(msg_block) > 8000:
        msg_block = msg_block[:8000] + "\n... [truncated]"

    prompt = f"""You are analyzing Telegram chat messages to build a personal wiki about {my_name}.

Chat: {chat_name}
Total messages from {my_name}: {len(my_msgs)}
Date range: {my_msgs[0]['date'][:10] if my_msgs else 'unknown'} to {my_msgs[-1]['date'][:10] if my_msgs else 'unknown'}

MESSAGES:
{msg_block}

Based on these messages, write a structured wiki article about what we learn about {my_name} from this chat. Focus on:
1. Relationship with {chat_name} (who are they to him? friend, family, colleague?)
2. Topics they discuss (what does he care about?)
3. His communication style in this chat (formal? casual? funny? serious?)
4. His opinions, beliefs, preferences revealed in conversation
5. Life events or plans mentioned
6. His personality traits visible in these messages
7. Interesting quotes or memorable things he said

Write in markdown format. Be specific — use actual examples from the messages.
Do NOT include the raw messages, only your analysis.
Keep it concise but insightful — aim for 300-500 words."""

    response = client.chat.completions.create(
        model=COMPILER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def compile_saved_messages(messages: list[dict], my_name: str = "Abdurakhmon") -> str:
    """Compile saved messages — these are bookmarks/notes to self."""
    my_msgs = [m for m in messages if len(m.get("text", "")) > 10]
    sampled = sample_messages(my_msgs, 300)

    msg_block = "\n".join(f"[{m['date']}] {m['text']}" for m in sampled)
    if len(msg_block) > 8000:
        msg_block = msg_block[:8000] + "\n... [truncated]"

    prompt = f"""You are analyzing {my_name}'s Telegram "Saved Messages" — things he saved for himself (bookmarks, notes, reminders, links, thoughts).

SAVED MESSAGES:
{msg_block}

Write a structured wiki article about what these saved messages reveal about {my_name}:
1. Topics and interests he saves content about
2. Goals or plans he's noting down
3. Resources and tools he's interested in
4. Patterns in what he saves (tech? career? personal?)
5. Any recurring themes

Write in markdown. Be specific. 300-500 words."""

    response = client.chat.completions.create(
        model=COMPILER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def compile_personal_channel(messages: list[dict], channel_name: str) -> str:
    """Compile a personal channel — these are his public thoughts."""
    sampled = sample_messages(messages, 300)

    msg_block = "\n".join(f"[{m['date']}] {m['text']}" for m in sampled)
    if len(msg_block) > 8000:
        msg_block = msg_block[:8000] + "\n... [truncated]"

    prompt = f"""You are analyzing {channel_name}, a personal Telegram channel by Abdurakhmon — his public posts and thoughts.

POSTS:
{msg_block}

Write a structured wiki article about what this channel reveals about Abdurakhmon:
1. What topics does he post about?
2. What's his public voice/persona like?
3. What opinions does he share publicly?
4. What themes recur?
5. How does this differ from private chats (if you can tell)?

Write in markdown. Be specific. 300-500 words."""

    response = client.chat.completions.create(
        model=COMPILER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def compile_big_history_overview(data: dict) -> str:
    """Compile an overview from the big TG history export."""
    chats = data.get("chats", {}).get("list", [])

    # Build a summary of all chats
    chat_summaries = []
    for chat in chats:
        name = chat.get("name", "?")
        chat_type = chat.get("type", "?")
        msg_count = len(chat.get("messages", []))
        if msg_count > 0:
            my_count = sum(1 for m in chat.get("messages", []) if m.get("from") == "Abdurakhmon")
            chat_summaries.append(f"- {name} ({chat_type}): {msg_count} msgs, {my_count} mine")

    summary_block = "\n".join(chat_summaries[:200])

    # Also get personal info if available
    personal_info = data.get("personal_information", {})
    about = data.get("about", "")

    prompt = f"""You are analyzing Abdurakhmon's full Telegram history export to build his personal wiki.

ABOUT/BIO: {about}
PERSONAL INFO: {json.dumps(personal_info, indent=2) if personal_info else 'Not available'}

CHAT LIST (showing active chats):
{summary_block}

Based on this overview, write a wiki article about:
1. His social circle — who does he talk to most? What types of relationships?
2. His communities — what groups is he in? What topics?
3. His channels — what does he follow/create?
4. Patterns — is he more active in groups or 1-on-1? What does this say about him?
5. Timeline — how has his Telegram usage evolved?

Write in markdown. Be analytical and insightful. 400-600 words."""

    response = client.chat.completions.create(
        model=COMPILER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def main():
    chat_dir = os.path.join(DATA_DIR, "chat_exports")
    wiki_path = Path(WIKI_DIR)
    wiki_path.mkdir(exist_ok=True)

    # Track what we compile
    compiled = []

    # 1. Individual chat exports
    for folder in sorted(os.listdir(chat_dir)):
        result_path = os.path.join(chat_dir, folder, "result.json")
        if not os.path.exists(result_path):
            continue

        # Determine output filename to check if already compiled
        if folder.startswith("my-big"):
            expected_file = wiki_path / f"social-overview-{folder}.md"
        elif folder == "saved-messages":
            expected_file = wiki_path / "saved-messages.md"
        elif folder == "my-tg-channel":
            expected_file = wiki_path / f"channel-{folder}.md"
        else:
            expected_file = wiki_path / f"chat-{folder}.md"

        if expected_file.exists():
            print(f"\nSkipping {folder} — already compiled ({expected_file.name})", flush=True)
            compiled.append(expected_file.name)
            continue

        print(f"\nProcessing: {folder}...", flush=True)

        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Big TG history export (has 'chats' key with many chats)
        if "chats" in data and folder.startswith("my-big"):
            print(f"  Big history export — compiling overview...", flush=True)
            try:
                article = compile_big_history_overview(data)
                out_file = wiki_path / f"social-overview-{folder}.md"
                out_file.write_text(f"# Social Overview — {folder}\n\n{article}", encoding="utf-8")
                compiled.append(f"social-overview-{folder}.md")
                print(f"  Saved: {out_file.name}", flush=True)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
            continue

        messages = extract_my_messages(data)
        if not messages:
            print(f"  No messages found, skipping.", flush=True)
            continue

        chat_name = data.get("name", folder)
        my_msgs = [m for m in messages if m.get("from") == "Abdurakhmon"]
        print(f"  {chat_name}: {len(messages)} msgs, {len(my_msgs)} mine", flush=True)

        try:
            # Choose the right compiler
            if folder == "saved-messages":
                article = compile_saved_messages(messages)
                filename = "saved-messages.md"
            elif folder == "my-tg-channel":
                article = compile_personal_channel(messages, chat_name)
                filename = f"channel-{folder}.md"
            else:
                article = compile_chat_to_wiki(chat_name, messages)
                filename = f"chat-{folder}.md"

            out_file = wiki_path / filename
            out_file.write_text(f"# {chat_name}\n\n{article}", encoding="utf-8")
            compiled.append(filename)
            print(f"  Saved: {filename}", flush=True)

        except Exception as e:
            print(f"  ERROR compiling {folder}: {e}", flush=True)

    # 2. Build an index
    print(f"\nBuilding index...", flush=True)
    index_lines = ["# Wiki Index\n", "## Core Profile"]
    for f in sorted(wiki_path.glob("*.md")):
        if f.name == "index.md":
            continue
        index_lines.append(f"- [{f.stem}]({f.name})")

    (wiki_path / "index.md").write_text("\n".join(index_lines), encoding="utf-8")

    print(f"\n=== DONE ===")
    print(f"Compiled {len(compiled)} articles into wiki/")
    print(f"Wiki files: {', '.join(compiled)}")


if __name__ == "__main__":
    main()
