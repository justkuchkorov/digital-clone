import hashlib
import sys
import time
from pathlib import Path
from datetime import datetime

_vendor_dir = Path(__file__).resolve().parent / ".vendor"
if sys.version_info[:2] == (3, 11) and _vendor_dir.exists() and str(_vendor_dir) not in sys.path:
    sys.path.insert(0, str(_vendor_dir))

import chromadb
from config import CHROMA_PATH, GEMINI_API_KEY, RAG_TOP_K, CHUNK_SIZE, CHUNK_OVERLAP
from config import COLLECTION_PROFILE, COLLECTION_CONVERSATIONS, COLLECTION_DOCUMENTS


class GeminiEmbeddingFunction:
    """Minimal Chroma embedding wrapper that avoids SDK adapter version issues."""

    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self._genai = None

    def _client(self):
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        if self._genai is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
        return self._genai

    def __call__(self, input):
        texts = [input] if isinstance(input, str) else list(input)
        all_embeddings = []
        for start in range(0, len(texts), 50):
            batch = texts[start:start + 50]
            for attempt in range(2):
                try:
                    resp = self._client().embed_content(model=self.model_name, content=batch)
                    embeddings = resp.get("embedding", [])
                    if embeddings and isinstance(embeddings[0], (int, float)):
                        embeddings = [embeddings]
                    all_embeddings.extend(embeddings)
                    break
                except Exception as e:
                    if attempt == 0 and ("429" in str(e) or "ResourceExhausted" in str(e)):
                        print("[MEMORY] Gemini embedding quota hit; waiting 65s...", flush=True)
                        time.sleep(65)
                        continue
                    raise
        return all_embeddings

    def name(self) -> str:
        return f"gemini:{self.model_name}"

    def embed_query(self, input):
        return self(input)

    def embed_documents(self, input):
        return self(input)


# Initialize ChromaDB
_client = chromadb.PersistentClient(path=CHROMA_PATH)
_embedding_fn = GeminiEmbeddingFunction(
    api_key=GEMINI_API_KEY,
    model_name="models/gemini-embedding-001"
)


def get_collection(name: str):
    """Get or create a ChromaDB collection."""
    return _client.get_or_create_collection(
        name=name,
        embedding_function=_embedding_fn
    )


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def add_texts(collection_name: str, texts: list[str], metadatas: list[dict] = None):
    """Add texts to a ChromaDB collection. Deduplicates by content hash."""
    collection = get_collection(collection_name)

    ids = [hashlib.md5(t.encode()).hexdigest() for t in texts]
    if metadatas is None:
        metadatas = [{"source": "unknown"}] * len(texts)

    # Upsert to handle deduplication
    collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas
    )
    return len(texts)


def add_conversation_memory(user_id: int, user_text: str, assistant_text: str = "") -> int:
    """Store a meaningful live chat turn in semantic conversation memory."""
    user_text = (user_text or "").strip()
    assistant_text = (assistant_text or "").strip()
    if not user_text:
        return 0

    doc = f"User: {user_text}"
    if assistant_text:
        doc += f"\nBrunof: {assistant_text}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metadata = {
        "source": "live_chat",
        "user_id": str(user_id),
        "created_at": now,
    }
    return add_texts(COLLECTION_CONVERSATIONS, [doc], [metadata])


def query_knowledge(query: str, n_results: int = RAG_TOP_K) -> str:
    """Query all collections and return merged results as formatted context."""
    all_results = []

    for col_name in [COLLECTION_PROFILE, COLLECTION_CONVERSATIONS, COLLECTION_DOCUMENTS]:
        try:
            collection = get_collection(col_name)
            if collection.count() == 0:
                continue

            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, collection.count())
            )

            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    distance = results["distances"][0][i] if results["distances"] else 999
                    source = col_name.replace("_", " ").title()
                    all_results.append((distance, source, doc))
        except Exception as e:
            print(f"[MEMORY] Error querying {col_name}: {e}")
            continue

    if not all_results:
        return "No relevant personal information found in the knowledge base."

    # Sort by distance (lower = more relevant)
    all_results.sort(key=lambda x: x[0])
    top_results = all_results[:n_results]

    # Format as context block
    context_parts = []
    for distance, source, doc in top_results:
        context_parts.append(f"[{source}]: {doc}")

    return "\n\n".join(context_parts)


def get_stats() -> dict:
    """Return document counts for all collections."""
    stats = {}
    for col_name in [COLLECTION_PROFILE, COLLECTION_CONVERSATIONS, COLLECTION_DOCUMENTS]:
        try:
            stats[col_name] = get_collection(col_name).count()
        except Exception:
            stats[col_name] = 0
    return stats
