import os
import sys

BASE_DIR = os.path.dirname(__file__)
VENDOR_DIR = os.path.join(BASE_DIR, ".vendor")
if sys.version_info[:2] == (3, 11) and os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

from dotenv import load_dotenv

load_dotenv()

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Telegram owner
OWNER_ID = int(os.getenv("OWNER_ID", "1946444733"))

# LLM
GROQ_MODEL = "llama-3.3-70b-versatile"

# Chat history
MAX_CHAT_HISTORY = 20
CONVERSATION_MEMORY_MIN_CHARS = 20

# Paths
WIKI_DIR = os.path.join(BASE_DIR, "wiki")
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

# RAG / memory
RAG_TOP_K = 5
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

# Chroma collections
COLLECTION_PROFILE = "profile"
COLLECTION_CONVERSATIONS = "conversations"
COLLECTION_DOCUMENTS = "documents"

# Google Workspace action bridge (gogcli)
GOG_ACCOUNT = os.getenv("GOG_ACCOUNT", "abdurakhmonkuchkorov@gmail.com")
GOG_PATH = os.getenv("GOG_PATH", os.path.join(BASE_DIR, ".tools", "gogcli", "gog.exe"))
