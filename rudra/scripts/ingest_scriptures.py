"""One-time ingestion script to populate ChromaDB with scripture texts.

NOTE: This script generates new unique chunk IDs each time it runs.
Re-running this script without clearing the ChromaDB collection first will add
duplicate entries for files that were already ingested.
"""

import sys
from pathlib import Path

# Add rudra root directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
RUDRA_DIR = SCRIPT_DIR.parent
if str(RUDRA_DIR) not in sys.path:
    sys.path.insert(0, str(RUDRA_DIR))

try:
    from memory.scriptures import _chunk_text, _get_collection, add_scripture_text
except ImportError:
    from rudra.memory.scriptures import _chunk_text, _get_collection, add_scripture_text


DATA_DIR = RUDRA_DIR / "data" / "scriptures"


def ingest_scriptures(data_dir: Path = DATA_DIR) -> dict[str, int]:
    """Read all .txt files from data_dir and ingest them into ChromaDB."""
    print("=" * 60)
    print("Rudra Scripture Ingestion")
    print("=" * 60)
    print(f"Scanning directory: {data_dir}")
    print(
        "WARNING: Re-running this script will add duplicate chunk entries "
        "if the collection is not reset."
    )
    print("-" * 60)

    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}")
        return {}

    txt_files = sorted(data_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {data_dir}.")
        print("Please place scraped scripture .txt files in this directory.")
        return {}

    collection = _get_collection()
    if collection is None:
        print("Error: Could not initialize ChromaDB collection (no embedding function available).")
        return {}

    initial_total_count = collection.count()
    print(f"Initial collection document count: {initial_total_count}\n")

    summary: dict[str, int] = {}

    for file_path in txt_files:
        source_name = file_path.stem
        print(f"Processing: {file_path.name} (source: '{source_name}')...")

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = file_path.read_text(encoding="latin-1")
            except Exception as exc:
                print(f"  [WARNING] Failed to read {file_path.name} due to encoding error: {exc}. Skipping.")
                continue
        except Exception as exc:
            print(f"  [WARNING] Could not read file {file_path.name}: {exc}. Skipping.")
            continue

        if not text.strip():
            print(f"  [WARNING] File {file_path.name} is empty. Skipping.")
            continue

        chunks = _chunk_text(text)
        num_chunks = len(chunks)

        if num_chunks == 0:
            print(f"  [WARNING] No valid chunks produced for {file_path.name}. Skipping.")
            continue

        try:
            add_scripture_text(source_name, text)
            print(f"  [SUCCESS] Ingested {num_chunks} chunk(s) from {file_path.name}")
            summary[source_name] = num_chunks
        except Exception as exc:
            print(f"  [ERROR] Failed to ingest {file_path.name}: {exc}")

    final_total_count = collection.count()
    print("\n" + "=" * 60)
    print("Ingestion Summary")
    print("=" * 60)
    for src, cnt in summary.items():
        print(f"  - {src}: {cnt} chunk(s)")
    print(f"\nTotal documents in collection now: {final_total_count}")
    return summary


if __name__ == "__main__":
    ingest_scriptures()
