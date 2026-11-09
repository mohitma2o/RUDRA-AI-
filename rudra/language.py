"""Language identification and voice selection for the legacy tray app."""

VOICE_MAP = {
    "hi": "hi-IN-MadhurNeural",
    "pa": "pa-IN-AmanNeural",
    "en": "en-IN-PrabhatNeural",
}


def detect_language(text: str) -> str:
    if not text:
        return "en"
    if any("\u0900" <= character <= "\u097F" for character in text):
        return "hi"
    if any("\u0A00" <= character <= "\u0A7F" for character in text):
        return "pa"
    return "en"


def _choose_voice(language: str) -> str:
    lang = (language or "").lower()
    if lang.startswith("hi"):
        return VOICE_MAP["hi"]
    if lang.startswith("pa"):
        return VOICE_MAP["pa"]
    return VOICE_MAP["en"]
