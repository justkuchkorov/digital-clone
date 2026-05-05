import sys
import re
import tempfile
import os
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent / ".vendor"
if sys.version_info[:2] == (3, 11) and VENDOR_DIR.exists() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

import telebot


def md_to_html(text: str) -> str:
    """Convert markdown bold/italic to HTML for Telegram."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text
from groq import Groq
from config import TELEGRAM_BOT_TOKEN, GROQ_API_KEY, OWNER_ID, WIKI_DIR
from brain import get_response, clear_history
import threading

sys.stdout.reconfigure(encoding="utf-8")

if not TELEGRAM_BOT_TOKEN:
    print("ERROR: Could not find TELEGRAM_BOT_TOKEN in .env file!")
    exit()

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
BOT_USERNAME = None  # fetched on startup

# Groq client for voice transcription (Whisper — free)
groq_client = Groq(api_key=GROQ_API_KEY)


def _is_group(message) -> bool:
    return message.chat.type in ("group", "supergroup")


def _is_directed_at_bot(message) -> bool:
    """Check if a group message is directed at the bot (mention or reply)."""
    # Reply to one of the bot's messages
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == bot.user.id:
            return True
    # @mention in text
    if message.text and BOT_USERNAME and f"@{BOT_USERNAME}" in message.text:
        return True
    # @mention in entities
    if message.entities:
        for ent in message.entities:
            if ent.type == "mention":
                mention = message.text[ent.offset:ent.offset + ent.length]
                if BOT_USERNAME and mention.lower() == f"@{BOT_USERNAME.lower()}":
                    return True
    return False


def _strip_mention(text: str) -> str:
    """Remove @botusername from the message text."""
    if not text or not BOT_USERNAME:
        return text
    return re.sub(rf'@{re.escape(BOT_USERNAME)}\s*', '', text, flags=re.IGNORECASE).strip()


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "<b>Hey, I'm your Digital Clone</b> — your AI second brain.\n\n"
        "I know you, your values, your goals. Talk to me about anything:\n"
        "- Life advice, career decisions\n"
        "- Vent about your day\n"
        "- Brainstorm ideas\n"
        "- Or just chat\n\n"
        "Commands:\n"
        "/wiki — list wiki pages\n"
        "/digest — update brain from recent chats\n"
        "/forget — clear conversation history\n"
        "/help — show this message"
    )
    bot.reply_to(message, welcome_text, parse_mode="HTML")


@bot.message_handler(commands=['digest'])
def handle_digest(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "only the boss can run this 🗿")
        return
    bot.reply_to(message, "digesting recent chats... give me a sec")

    def _run_digest():
        try:
            from auto_update import run_all
            run_all()
            bot.send_message(message.chat.id, "brain updated. i know more now 🧠")
        except Exception as e:
            bot.send_message(message.chat.id, f"digest failed: {e}")

    threading.Thread(target=_run_digest, daemon=True).start()


@bot.message_handler(commands=['forget'])
def handle_forget(message):
    clear_history(message.from_user.id)
    bot.reply_to(message, "Done. Fresh start — what's on your mind?")


@bot.message_handler(commands=['wiki'])
def handle_wiki(message):
    wiki_path = Path(WIKI_DIR)
    if not wiki_path.exists():
        bot.reply_to(message, "No wiki found.")
        return
    files = sorted(wiki_path.glob("*.md"))
    if not files:
        bot.reply_to(message, "Wiki is empty.")
        return
    lines = ["<b>Wiki Pages:</b>\n"]
    for f in files:
        size = f.stat().st_size
        lines.append(f"  <code>{f.name}</code> — {size:,} bytes")
    bot.reply_to(message, "\n".join(lines), parse_mode="HTML")


@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    # In groups, only respond to voice if it's a reply to the bot
    group = _is_group(message)
    if group:
        if not (message.reply_to_message and message.reply_to_message.from_user
                and message.reply_to_message.from_user.id == bot.user.id):
            return

    label = f"{message.from_user.first_name} (group: {message.chat.title})" if group else message.from_user.first_name
    print(f"\n--> Voice message from {label}", flush=True)
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        # Download the voice file
        file_info = bot.get_file(message.voice.file_id)
        audio_bytes = bot.download_file(file_info.file_path)

        # Transcribe with Groq Whisper (free)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=("voice.ogg", audio_file.read()),
                model="whisper-large-v3",
            )
        os.unlink(tmp_path)

        text = transcription.text.strip()
        print(f"    Transcribed: {text}", flush=True)

        # Process like a normal message
        reply = get_response(
            message.from_user.id, text, is_group=group,
            sender_name=message.from_user.first_name or "",
            sender_username=message.from_user.username or "",
            chat_id=message.chat.id if group else None,
        )
        bot.send_message(
            message.chat.id,
            text=md_to_html(reply),
            reply_to_message_id=message.message_id if group else None,
            parse_mode="HTML"
        )
        print(f"--> Replied to voice successfully", flush=True)

    except Exception as e:
        print(f"\n[ERROR] Voice handling: {e}", flush=True)
        bot.send_message(
            message.chat.id,
            "Couldn't process your voice message. Try again or type it out.",
            parse_mode="HTML"
        )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    # In groups, only respond when mentioned or replied to
    group = _is_group(message)
    if group and not _is_directed_at_bot(message):
        return

    text = message.text or ""
    if group:
        text = _strip_mention(text)
    if not text.strip():
        return

    label = f"{message.from_user.first_name} (group: {message.chat.title})" if group else message.from_user.first_name
    print(f"\n--> Received from {label}: {text}", flush=True)
    bot.send_chat_action(message.chat.id, 'typing')

    # Extract replied message context
    reply_text = ""
    reply_sender = ""
    if message.reply_to_message:
        rm = message.reply_to_message
        if rm.text and rm.from_user and rm.from_user.id != bot.user.id:
            reply_text = rm.text
            reply_sender = rm.from_user.first_name or "someone"

    try:
        reply = get_response(
            message.from_user.id, text, is_group=group,
            sender_name=message.from_user.first_name or "",
            sender_username=message.from_user.username or "",
            reply_text=reply_text, reply_sender=reply_sender,
            chat_id=message.chat.id if group else None,
        )
        bot.send_message(
            message.chat.id,
            text=md_to_html(reply),
            reply_to_message_id=message.message_id if group else None,
            parse_mode="HTML"
        )
        print(f"--> Replied successfully", flush=True)

    except Exception as e:
        print(f"\n[ERROR] {e}", flush=True)
        bot.send_message(
            message.chat.id,
            "Something went wrong on my end. Give me a sec and try again.",
            parse_mode="HTML"
        )


if __name__ == "__main__":
    me = bot.get_me()
    BOT_USERNAME = me.username
    print(f"Digital Clone is online (@{BOT_USERNAME}). Works in private chat + groups.", flush=True)
    bot.remove_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
