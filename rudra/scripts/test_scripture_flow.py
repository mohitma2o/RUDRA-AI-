"""Test the end-to-end scripture grounding and voice synthesis flow."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from memory.scriptures import query as query_scripture
from llm import query_llm
from tts import speak_text


def test_scripture_grounding():
    question = "What does the Gita say about doing your duty?"
    print(f"Question: {question}\n")

    # Step 1: Scripture retrieval
    hits = query_scripture(question, k=3)
    print(f"Retrieved {len(hits)} scripture passage(s):")
    for idx, hit in enumerate(hits, 1):
        src = hit.get("source", "unknown")
        snippet = hit.get("text", "")[:120].replace("\n", " ")
        print(f"  {idx}. [{src}] {snippet}...")

    assert len(hits) > 0, "No scripture passages retrieved!"

    scripture_context = [
        f"{h.get('source', 'scripture')}: {h.get('text', '')}"
        for h in hits
        if h.get("text")
    ]

    # Step 2: LLM generation with persona and scripture context
    print("\nQuerying LLM with scripture context...")
    response = query_llm(question, context=scripture_context, language="en")
    print("\n" + "=" * 60)
    print("Rudra's Response:")
    print("=" * 60)
    print(response)
    print("=" * 60)

    # Step 3: Real spoken TTS interaction
    print("\nPlaying spoken audio response via Edge-TTS and Windows audio...")
    speak_text(response, language="en")
    print("Spoken audio completed successfully!")


if __name__ == "__main__":
    test_scripture_grounding()
