import hashlib
import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from config import CHROMA_PATH, GEMINI_API_KEY, RAG_TOP_K, CHUNK_SIZE, CHUNK_OVERLAP
from config import COLLECTION_PROFILE, COLLECTION_CONVERSATIONS, COLLECTION_DOCUMENTS

# Initialize ChromaDB
_client = chromadb.PersistentClient(path=CHROMA_PATH)
_embedding_fn = GoogleGenerativeAiEmbeddingFunction(
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
