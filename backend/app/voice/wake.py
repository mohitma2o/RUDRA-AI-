"""Wake word detection with fuzzy matching for multi-language variants."""

import re
from rapidfuzz import fuzz

WAKE_WORDS = [
    "rudra", "rudhra", "rudraa", "rudar", "rudrah", "roodra", "rudro",
    # Devanagari (Hindi)
    "\u0930\u0941\u0926\u094d\u0930", "\u0930\u0941\u0926\u094d\u0930\u093e",
    # Gurmukhi (Punjabi)
    "\u0a30\u0a41\u0a26\u0a30", "\u0a30\u0a41\u0a71\u0a26\u0a30",
]

# Only these must NOT match (to avoid false positives on similar words)
FALSE_POSITIVES = {"rude", "rudder", "rut", "ruler", "raider"}


def find_wake(text: str) -> str | None:
    """Return the matched wake token if text contains the wake word, else None."""
    if not text:
        return None
    t = text.lower().strip()

    # 1. Exact substring match (fast path)
    for w in WAKE_WORDS:
        if w in t:
            return w

    # 2. Fuzzy match on the first 3 tokens (name is usually near the start)
    tokens = re.findall(r"\w+", t)[:3]
    for tok in tokens:
        if tok in FALSE_POSITIVES:
            continue
        best = max(fuzz.ratio(tok, w) for w in WAKE_WORDS[:6])  # Latin variants
        if best >= 80:
            return tok

    return None


def strip_wake(text: str, wake: str) -> str:
    """Remove the wake word from the transcript so the command is clean."""
    return re.sub(re.escape(wake), "", text, count=1, flags=re.I).strip(" ,.!?-\u0964")
