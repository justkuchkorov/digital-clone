"""Data ingestion script for Digital Clone knowledge base."""
import sys
import os
import json
import argparse
from pathlib import Path
from config import (
    DATA_DIR,
    WIKI_DIR,
    COLLECTION_PROFILE,
    COLLECTION_CONVERSATIONS,
    COLLECTION_DOCUMENTS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from memory import add_texts, chunk_text, get_stats

sys.stdout.reconfigure(encoding="utf-8")


def ingest_profile():
    """Ingest the personal profile document."""
    profile_path = os.path.join(DATA_DIR, "profile.md")

    if not os.path.exists(profile_path):
        print(f"Profile not found at {profile_path}")
        print("Create data/profile.md with your personal info first.")
        return

    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by markdown headings for semantic sections
    sections = []
    current_section = ""
    current_heading = "general"

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section.strip():
                sections.append((current_heading, current_section.strip()))
            current_heading = line.replace("## ", "").strip().lower()
            current_section = ""
        elif line.startswith("# "):
            current_heading = line.replace("# ", "").strip().lower()
        else:
            current_section += line + "\n"

    if current_section.strip():
        sections.append((current_heading, current_section.strip()))

    # Chunk each section and add to DB
    all_chunks = []
    all_metadatas = []

    for heading, text in sections:
        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        for chunk in chunks:
            all_chunks.append(chunk)
            all_metadatas.append({"source": "profile", "section": heading})

    count = add_texts(COLLECTION_PROFILE, all_chunks, all_metadatas)
    print(f"Ingested profile: {count} chunks from {len(sections)} sections")


def ingest_telegram_chats():
    """Ingest Telegram chat exports (JSON format)."""
    chat_dir = os.path.join(DATA_DIR, "chat_exports")

    if not os.path.exists(chat_dir):
        print(f"Chat exports directory not found at {chat_dir}")
        return

    json_files = list(Path(chat_dir).glob("*.json"))
    if not json_files:
        # Also check for result.json inside subdirectories (TG Desktop export format)
        json_files = list(Path(chat_dir).glob("**/result.json"))

    if not json_files:
        print("No JSON files found in data/chat_exports/")
        print("Export your Telegram chats and place the JSON files there.")
        return

    total_chunks = 0

    for json_file in json_files:
        print(f"Processing: {json_file.name}")

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = []

        # Handle Telegram Desktop export format
        if "chats" in data and "list" in data["chats"]:
            for chat in data["chats"]["list"]:
                chat_name = chat.get("name", "Unknown")
                for msg in chat.get("messages", []):
                    text = msg.get("text", "")
                    # text can be a list of objects in TG exports
                    if isinstance(text, list):
                        text = " ".join(
                            part if isinstance(part, str) else part.get("text", "")
                            for part in text
                        )
                    if text.strip():
                        messages.append({
                            "text": text.strip(),
                            "date": msg.get("date", ""),
                            "chat": chat_name,
                            "from": msg.get("from", "")
                        })

        # Handle single chat export format
        elif "messages" in data:
            chat_name = data.get("name", json_file.stem)
            for msg in data["messages"]:
                text = msg.get("text", "")
                if isinstance(text, list):
                    text = " ".join(
                        part if isinstance(part, str) else part.get("text", "")
                        for part in text
                    )
                if text.strip():
                    messages.append({
                        "text": text.strip(),
                        "date": msg.get("date", ""),
                        "chat": chat_name,
                        "from": msg.get("from", "")
                    })

        if not messages:
            print(f"  No messages found in {json_file.name}")
            continue

        # Group messages into conversation chunks (by time proximity)
        chunks = []
        metadatas = []
        current_chunk = []
        current_date = ""

        for msg in messages:
            current_chunk.append(f"{msg['from']}: {msg['text']}")
            if not current_date:
                current_date = msg["date"]

            # Group ~10 messages per chunk
            if len(current_chunk) >= 10:
                chunk_text_str = "\n".join(current_chunk)
                chunks.append(chunk_text_str)
                metadatas.append({
                    "source": "telegram",
                    "chat": msg["chat"],
                    "date": current_date
                })
                current_chunk = []
                current_date = ""

        # Don't forget the last chunk
        if current_chunk:
            chunk_text_str = "\n".join(current_chunk)
            chunks.append(chunk_text_str)
            metadatas.append({
                "source": "telegram",
                "chat": messages[-1]["chat"],
                "date": current_date
            })

        count = add_texts(COLLECTION_CONVERSATIONS, chunks, metadatas)
        total_chunks += count
        print(f"  {count} chunks from {len(messages)} messages")

    print(f"Total chat chunks ingested: {total_chunks}")


def ingest_wiki_pages():
    """Ingest compiled wiki markdown pages into the document collection."""
    wiki_path = Path(WIKI_DIR)
    if not wiki_path.exists():
        print(f"Wiki directory not found at {wiki_path}")
        return

    wiki_files = [
        f for f in sorted(wiki_path.glob("*.md"))
        if f.name not in ("index.md",) and f.read_text(encoding="utf-8").strip()
    ]
    if not wiki_files:
        print("No wiki pages found to ingest.")
        return

    all_chunks = []
    all_metadatas = []
    for wiki_file in wiki_files:
        content = wiki_file.read_text(encoding="utf-8")
        page_chunks = chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
        for chunk in page_chunks:
            all_chunks.append(chunk)
            all_metadatas.append({"source": "wiki", "page": wiki_file.name})

    count = add_texts(COLLECTION_DOCUMENTS, all_chunks, all_metadatas)
    print(f"Ingested wiki: {count} chunks from {len(wiki_files)} pages")


def main():
    parser = argparse.ArgumentParser(description="Ingest data into Digital Clone knowledge base")
    parser.add_argument("--profile", action="store_true", help="Ingest personal profile")
    parser.add_argument("--chats", action="store_true", help="Ingest Telegram chat exports")
    parser.add_argument("--wiki", action="store_true", help="Ingest compiled wiki pages")
    parser.add_argument("--all", action="store_true", help="Ingest everything")
    parser.add_argument("--stats", action="store_true", help="Show knowledge base stats")
    args = parser.parse_args()

    if args.stats:
        stats = get_stats()
        print("Knowledge Base Stats:")
        for name, count in stats.items():
            print(f"  {name}: {count} documents")
        return

    if args.all or (not args.profile and not args.wiki and not args.chats):
        # Default: ingest everything
        print("=== Ingesting Profile ===")
        ingest_profile()
        print("\n=== Ingesting Wiki ===")
        ingest_wiki_pages()
        print("\n=== Ingesting Telegram Chats ===")
        ingest_telegram_chats()
    else:
        if args.profile:
            ingest_profile()
        if args.wiki:
            ingest_wiki_pages()
        if args.chats:
            ingest_telegram_chats()

    print("\n=== Final Stats ===")
    stats = get_stats()
    for name, count in stats.items():
        print(f"  {name}: {count} documents")


if __name__ == "__main__":
    main()
