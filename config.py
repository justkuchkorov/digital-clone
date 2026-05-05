import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# LLM
GROQ_MODEL = "llama-3.3-70b-versatile"

# Chat history
MAX_CHAT_HISTORY = 20

# Paths
BASE_DIR = os.path.dirname(__file__)
WIKI_DIR = os.path.join(BASE_DIR, "wiki")
DATA_DIR = os.path.join(BASE_DIR, "data")
