"""ChromaDB scripture RAG wrapper for relevant passage retrieval."""

import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError as exc:
    raise RuntimeError(
        "chromadb is required for scripture RAG. Install with `pip install chromadb`."
    ) from exc

BASE_DIR = Path(__file__).parent.parent
DOTENV_PATH = BASE_DIR / ".env"
if DOTENV_PATH.exists():
    load_dotenv(dotenv_path=DOTENV_PATH)

CHROMA_DB_PATH = Path(os.getenv("CHROMA_DB_PATH", BASE_DIR / "rudra_chroma"))
CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
COLLECTION_NAME = "scriptures"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

_client: Any = None
_collection: Any = None


def _load_embedding_function() -> Any:
    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    except Exception:
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                return embedding_functions.OpenAIEmbeddingFunction(
                    api_key=openai_key,
                    model_name=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                )
            except Exception as exc:
                raise RuntimeError(
                    "Failed to initialize OpenAI embeddings. Check OPENAI_API_KEY and model settings."
                ) from exc

    raise RuntimeError(
        "No embedding backend available. Install sentence-transformers or set OPENAI_API_KEY."
    )


def _get_client() -> Any:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    return _client


def _get_collection() -> Any:
    global _collection
    if _collection is None:
        client = _get_client()
        embedding_fn = _load_embedding_function()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    return _collection


def _chunk_text(text: str, max_chars: int = 900) -> list[str]:
    chunks: list[str] = []
    current = ""

    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) <= max_chars:
            if current and len(current) + len(paragraph) + 2 <= max_chars:
                current = f"{current}\n\n{paragraph}"
            else:
                if current:
                    chunks.append(current.strip())
                current = paragraph
            continue

        sentences = paragraph.split(". ")
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = f"{current}. {sentence}" if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current.strip())
                current = ""

            if len(sentence) <= max_chars:
                current = sentence
            else:
                for i in range(0, len(sentence), max_chars):
                    chunk = sentence[i : i + max_chars].strip()
                    if chunk:
                        chunks.append(chunk)

    if current:
        chunks.append(current.strip())

    return chunks


def add_scripture_text(source_name: str, text: str) -> None:
    """Add scripture text to the ChromaDB collection with source attribution."""
    if not text or not text.strip():
        return

    collection = _get_collection()
    chunks = _chunk_text(text)
    if not chunks:
        return

    ids = [f"{source_name}-{uuid.uuid4().hex[:8]}-{idx}" for idx in range(len(chunks))]
    metadatas = [
        {"source": source_name, "chunk_index": idx, "length": len(chunk)}
        for idx, chunk in enumerate(chunks)
    ]

    collection.add(
        ids=ids,
        metadatas=metadatas,
        documents=chunks,
    )


def query(question: str, k: int = 3) -> list[dict[str, Any]]:
    """Return the top scripture passages relevant to the question."""
    if not question or not question.strip():
        return []

    collection = _get_collection()
    results = collection.query(
        query_texts=[question],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {
            "source": metadata.get("source") if isinstance(metadata, dict) else None,
            "text": document,
            "score": float(distance) if distance is not None else None,
            "metadata": metadata,
        }
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]
