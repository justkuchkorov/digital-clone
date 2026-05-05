"""
Google Takeout Compiler — extracts wiki pages from Google Drive metadata and Gmail.
"""
import os
import sys
import mailbox
import email.utils
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from groq import Groq
from config import GROQ_API_KEY, WIKI_DIR

sys.stdout.reconfigure(encoding="utf-8")

client = Groq(api_key=GROQ_API_KEY)
COMPILER_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

GOOGLE_DIR = os.path.join(os.path.dirname(__file__), "data", "google-takeout", "Takeout")
DRIVE_DIR = os.path.join(GOOGLE_DIR, "Drive")
MAIL_DIR = os.path.join(GOOGLE_DIR, "Mail")
wiki_path = Path(WIKI_DIR)


def compile_drive_overview():
    """Compile a wiki page from Google Drive file listing."""
    if wiki_path.joinpath("google-drive.md").exists():
        print("Skipping Drive — already compiled", flush=True)
        return

    files = []
    for root, dirs, flist in os.walk(DRIVE_DIR):
        for f in flist:
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, DRIVE_DIR)
            size = os.path.getsize(fp)
            ext = os.path.splitext(f)[1].lower()
            files.append((rel, size, ext))

    # Build a compact listing
    listing = []
    for rel, size, ext in sorted(files):
        size_str = f"{size // 1024}KB" if size > 1024 else f"{size}B"
        listing.append(f"- {rel} ({size_str}, {ext})")

    file_block = "\n".join(listing)
    if len(file_block) > 7000:
        file_block = file_block[:7000] + "\n... [truncated]"

    ext_counts = Counter(ext for _, _, ext in files)
    ext_summary = ", ".join(f"{ext}: {c}" for ext, c in ext_counts.most_common())

    prompt = f"""Analyze Abdurakhmon's Google Drive files to build a personal wiki article about him.

FILE TYPES: {ext_summary}
TOTAL FILES: {len(files)}

ALL FILES:
{file_block}

Write a structured wiki article about what these files reveal about Abdurakhmon:
1. Academic life — what courses, exams, assignments does he have?
2. Career preparation — CVs, motivation letters, applications
3. Personal interests — any non-academic files?
4. Religious/spiritual life — any related files?
5. Language learning — any evidence?
6. Key documents that stand out
7. Organization patterns — is he organized or messy?

Be specific — reference actual filenames. Write in markdown. 400-600 words."""

    print("Compiling Drive overview...", flush=True)
    response = client.chat.completions.create(
        model=COMPILER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )
    article = response.choices[0].message.content
    out = wiki_path / "google-drive.md"
    out.write_text(f"# Google Drive Overview\n\n{article}", encoding="utf-8")
    print(f"  Saved: {out.name}", flush=True)


def compile_email_overview():
    """Compile a wiki page from Gmail mbox — metadata only (subjects, senders, dates)."""
    if wiki_path.joinpath("google-email.md").exists():
        print("Skipping Email — already compiled", flush=True)
        return

    mbox_path = os.path.join(MAIL_DIR, "All mail Including Spam and Trash.mbox")
    if not os.path.exists(mbox_path):
        print("No mbox file found, skipping email.", flush=True)
        return

    print("Parsing mbox (this may take a minute)...", flush=True)

    # Parse email metadata (not bodies — too large)
    senders = Counter()
    recipients = Counter()
    subjects = []
    dates = []
    my_sent = 0
    total = 0
    labels_counter = Counter()

    mbox = mailbox.mbox(mbox_path)
    for i, msg in enumerate(mbox):
        total += 1
        from_addr = msg.get("From", "")
        to_addr = msg.get("To", "")
        subject = msg.get("Subject", "(no subject)")
        date_str = msg.get("Date", "")
        labels = msg.get("X-Gmail-Labels", "")

        # Extract email address from "Name <email>" format
        _, from_email = email.utils.parseaddr(from_addr)
        from_email = from_email.lower()

        if "kuchkorov" in from_email or "abdurakhmon" in from_email:
            my_sent += 1

        senders[from_email] += 1
        if to_addr:
            _, to_email = email.utils.parseaddr(to_addr)
            recipients[to_email.lower()] += 1

        if labels:
            for label in labels.split(","):
                labels_counter[label.strip()] += 1

        # Sample subjects (every 50th for overview)
        if i % 50 == 0 and subject:
            try:
                subjects.append(subject[:100])
            except:
                pass

        # Parse date for timeline
        if date_str:
            try:
                dt = email.utils.parsedate_to_datetime(date_str)
                dates.append(dt.year)
            except:
                pass

        # Progress
        if total % 5000 == 0:
            print(f"  Processed {total} emails...", flush=True)

    mbox.close()

    print(f"  Total: {total} emails, {my_sent} sent by Abdurakhmon", flush=True)

    # Build summary for LLM
    top_senders = senders.most_common(30)
    top_recipients = recipients.most_common(20)
    year_dist = Counter(dates)
    sampled_subjects = subjects[:60]

    summary = f"""GMAIL OVERVIEW FOR ABDURAKHMON:
Total emails: {total}
Sent by Abdurakhmon: {my_sent}

TOP SENDERS (who emails him most):
{chr(10).join(f'  {addr}: {c} emails' for addr, c in top_senders)}

TOP RECIPIENTS (who he emails most):
{chr(10).join(f'  {addr}: {c} emails' for addr, c in top_recipients)}

EMAILS BY YEAR:
{chr(10).join(f'  {y}: {c} emails' for y, c in sorted(year_dist.items()))}

GMAIL LABELS:
{chr(10).join(f'  {l}: {c}' for l, c in labels_counter.most_common(20))}

SAMPLE SUBJECTS (every 50th email):
{chr(10).join(f'  - {s}' for s in sampled_subjects)}"""

    if len(summary) > 7500:
        summary = summary[:7500] + "\n... [truncated]"

    prompt = f"""Analyze Abdurakhmon's Gmail data to build a personal wiki article about him.

{summary}

Write a structured wiki article about what his email reveals:
1. Communication patterns — who does he email most? What organizations?
2. Career/job hunting — any applications, recruiters, companies?
3. Academic life — university emails, professors, submissions?
4. Services and subscriptions — what does he use?
5. Timeline — how has his email usage evolved?
6. Notable patterns or insights

Be specific — reference actual email addresses/domains. Write in markdown. 400-600 words."""

    print("Compiling email overview...", flush=True)
    response = client.chat.completions.create(
        model=COMPILER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )
    article = response.choices[0].message.content
    out = wiki_path / "google-email.md"
    out.write_text(f"# Gmail Overview\n\n{article}", encoding="utf-8")
    print(f"  Saved: {out.name}", flush=True)


if __name__ == "__main__":
    wiki_path.mkdir(exist_ok=True)
    compile_drive_overview()
    compile_email_overview()
    print("\n=== Google Takeout compilation done ===", flush=True)
