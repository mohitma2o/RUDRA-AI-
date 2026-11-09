"""Deterministic creator identity responses shared by both Rudra runtimes."""

import re
import unicodedata


CREATOR_NAME = "Mohit Mattoo"

_ENGLISH_PATTERNS = (
    r"\bwho\s+(?:made|created|built|developed|designed|coded)\s+you\b",
    r"\bwho\s+is\s+(?:your|the)\s+(?:creator|developer|author|owner|designer)\b",
    r"\bwho\s+owns\s+you\b",
    r"\bwho\s+is\s+your\s+father\b",
)
_HINDI_PATTERNS = (
    r"\b(?:tumhe|tumhein|tume|tujhe|aapko)\s+kisne\s+banaya(?:\s+hai)?\b",
    r"\bkisne\s+banaya(?:\s+hai)?\s+(?:tumko|tumhe|aapko)\b",
    r"(?:^|\s)(?:तुम्हे|तुम्हें|आपको)\s*किसने\s*बनाया(?:\s*है)?(?=\s|$)",
    r"(?:^|\s)किसने\s*बनाया(?:\s*है)?\s*(?:तुम्हे|तुम्हें|आपको)(?=\s|$)",
)
_PUNJABI_PATTERNS = (
    r"\b(?:tuhanu|tainu)\s+(?:kine|kisne)\s+(?:banaya|bnaya|banaiya)\b",
    r"\b(?:kine|kisne)\s+(?:banaya|bnaya|banaiya)\s+(?:tuhanu|tainu)\b",
    r"\bkine\s+(?:banaya|bnaya|banaiya)\b",
    r"(?:^|\s)ਤੁਹਾਨੂੰ\s*ਕਿਨੇ\s*ਬਣਾਇਆ(?=\s|$)",
    r"(?:^|\s)ਤੁਹਾਨੂੰ\s*ਕਿਸਨੇ\s*ਬਣਾਇਆ(?=\s|$)",
    r"(?:^|\s)ਤੈਨੂੰ\s*ਕਿਸਨੇ\s*ਬਣਾਇਆ(?=\s|$)",
)
_PATTERNS = tuple(
    (language, re.compile(pattern, re.IGNORECASE))
    for language, patterns in (
        ("en", _ENGLISH_PATTERNS),
        ("hi", _HINDI_PATTERNS),
        ("pa", _PUNJABI_PATTERNS),
    )
    for pattern in patterns
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).casefold()
    cleaned = "".join(
        char if unicodedata.category(char)[0] in {"L", "M", "N"} or char.isspace() else " "
        for char in normalized
    )
    return " ".join(cleaned.split())


def check_creator_query(user_input: str) -> tuple[bool, str]:
    """Return a fixed, language-matched response for recognized creator questions."""
    if not isinstance(user_input, str) or not user_input.strip():
        return False, ""

    text = _normalize(user_input)
    language = next(
        (lang for lang, pattern in _PATTERNS if pattern.search(text)),
        None,
    )
    if language is None:
        return False, ""

    if language == "hi":
        return True, f"Mujhe {CREATOR_NAME} ne banaya hai. Main unka AI assistant RUDRA hoon!"
    if language == "pa":
        if any("\u0a00" <= char <= "\u0a7f" for char in text):
            return True, f"ਮੈਨੂੰ {CREATOR_NAME} ਨੇ ਬਣਾਇਆ ਹੈ। ਮੈਂ ਉਹਨਾਂ ਦਾ AI ਸਹਾਇਕ RUDRA ਹਾਂ!"
        return True, f"Mainu {CREATOR_NAME} ne banaya hai. Main unaa da AI assistant RUDRA haan!"
    return True, (
        f"I was created and developed by {CREATOR_NAME}. "
        "I am RUDRA, his personal AI assistant!"
    )


def creator_response_language(user_input: str, default: str = "en") -> str:
    """Return the response voice language when a creator query is recognized."""
    if not isinstance(user_input, str) or not user_input.strip():
        return default
    text = _normalize(user_input)
    for language, pattern in _PATTERNS:
        if pattern.search(text):
            return language
    return default
