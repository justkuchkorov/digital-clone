"""
Instagram DM Compiler — analyzes DM conversations for the wiki.
"""
import json
import sys
import os
from pathlib import Path
from groq import Groq
from config import GROQ_API_KEY, WIKI_DIR

sys.stdout.reconfigure(encoding="utf-8")

client = Groq(api_key=GROQ_API_KEY)
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MY_NAME = "justkuchkorov"

INBOX_DIR = r"C:\Users\abdur\Downloads\instagram-justkuchkorov\your_instagram_activity\messages\inbox"
wiki_path = Path(WIKI_DIR)


def decode_instagram_text(text):
    """Fix Instagram's broken UTF-8 encoding."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def load_conversation(folder):
    """Load all messages from a conversation folder."""
    messages = []
    i = 1
    while True:
        fp = os.path.join(INBOX_DIR, folder, f"message_{i}.json")
        if not os.path.exists(fp):
            break
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if i == 1:
            title = decode_instagram_text(data.get("title", folder))
        messages.extend(data.get("messages", []))
        i += 1
    # Messages are in reverse chronological order in Instagram exports
    messages.reverse()
    return title if i > 1 else folder, messages


def sample_messages(messages, max_msgs=120):
    """Sample messages evenly."""
    if len(messages) <= max_msgs:
        return messages
    step = len(messages) // max_msgs
    return messages[::step][:max_msgs]


def compile_dm(title, messages):
    """Compile a DM conversation into a wiki article."""
    my_msgs = [m for m in messages if m.get("sender_name") == MY_NAME]
    other_msgs = [m for m in messages if m.get("sender_name") != MY_NAME]

    sampled_my = sample_messages(my_msgs, 60)
    sampled_other = sample_messages(other_msgs, 30)

    msg_block = ""
    for m in sampled_my:
        content = m.get("content", "")
        if not content or len(content) < 3:
            continue
        content = decode_instagram_text(content)
        msg_block += f"[Abdurakhmon]: {content}\n"

    msg_block += "\n--- OTHER PERSON ---\n"
    for m in sampled_other:
        content = m.get("content", "")
        if not content or len(content) < 3:
            continue
        content = decode_instagram_text(content)
        sender = decode_instagram_text(m.get("sender_name", ""))
        msg_block += f"[{sender}]: {content}\n"

    if len(msg_block) > 7000:
        msg_block = msg_block[:7000] + "\n... [truncated]"

    prompt = f"""Analyze this Instagram DM conversation between Abdurakhmon (username: justkuchkorov) and {title}.
Total messages: {len(messages)} ({len(my_msgs)} from Abdurakhmon)

MESSAGES:
{msg_block}

Write a concise wiki article (200-350 words) about what this conversation reveals about Abdurakhmon:
1. Who is {title} to him? (friend, classmate, family?)
2. What do they talk about?
3. Communication style in this chat
4. Any interesting facts or personality traits revealed
5. Notable quotes if any

Write in markdown. Be specific."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
    )
    return response.choices[0].message.content


def compile_overview(all_convos):
    """Compile an overview of all DM conversations."""
    summary = "Instagram DM Overview for Abdurakhmon (justkuchkorov):\n\n"
    summary += f"Total conversations: {len(all_convos)}\n\n"
    summary += "Top conversations by message count:\n"
    for total, mine, title, folder in all_convos[:40]:
        summary += f"- {title}: {total} msgs ({mine} mine)\n"

    if len(summary) > 6000:
        summary = summary[:6000]

    prompt = f"""{summary}

Write a wiki article (300-400 words) about Abdurakhmon's Instagram social patterns:
1. Who are his closest Instagram friends? (most active DMs)
2. What communities/groups is he part of?
3. Any patterns (mostly Uzbek friends? international? classmates?)
4. How active is he on Instagram DMs vs other platforms?

Write in markdown. Be analytical."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
    )
    return response.choices[0].message.content


def main():
    wiki_path.mkdir(exist_ok=True)

    # Skip if overview already compiled
    if wiki_path.joinpath("instagram-dms-overview.md").exists():
        print("Overview already compiled, skipping.", flush=True)
    else:
        # Scan all conversations
        print("Scanning all conversations...", flush=True)
        all_convos = []
        for folder in sorted(os.listdir(INBOX_DIR)):
            fp = os.path.join(INBOX_DIR, folder, "message_1.json")
            if not os.path.exists(fp):
                continue
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = decode_instagram_text(data.get("title", folder))
            msgs = data.get("messages", [])
            my_msgs = sum(1 for m in msgs if m.get("sender_name") == MY_NAME)
            all_convos.append((len(msgs), my_msgs, title, folder))

        all_convos.sort(reverse=True)

        # Compile overview
        print("Compiling DM overview...", flush=True)
        overview = compile_overview(all_convos)
        out = wiki_path / "instagram-dms-overview.md"
        out.write_text(f"# Instagram DMs Overview\n\n{overview}", encoding="utf-8")
        print(f"  Saved: {out.name}", flush=True)

    # Compile top 10 individual DMs (most active)
    print("\nScanning for top DMs to compile...", flush=True)
    all_convos = []
    for folder in sorted(os.listdir(INBOX_DIR)):
        fp = os.path.join(INBOX_DIR, folder, "message_1.json")
        if not os.path.exists(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        title = decode_instagram_text(data.get("title", folder))
        msgs = data.get("messages", [])
        my_msgs = sum(1 for m in msgs if m.get("sender_name") == MY_NAME)
        all_convos.append((len(msgs), my_msgs, title, folder))

    all_convos.sort(reverse=True)

    compiled = 0
    for total, mine, title, folder in all_convos[:12]:
        if total < 100:
            break

        safe_name = folder.split("_")[0][:20]
        out_file = wiki_path / f"instagram-dm-{safe_name}.md"
        if out_file.exists():
            print(f"Skipping {title} — already compiled", flush=True)
            continue

        print(f"\nCompiling: {title} ({total} msgs, {mine} mine)...", flush=True)
        try:
            title_full, messages = load_conversation(folder)
            article = compile_dm(title_full, messages)
            out_file.write_text(f"# Instagram DM: {title_full}\n\n{article}", encoding="utf-8")
            compiled += 1
            print(f"  Saved: {out_file.name}", flush=True)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)

    print(f"\n=== Done! Compiled {compiled} new DM articles ===", flush=True)


if __name__ == "__main__":
    main()
