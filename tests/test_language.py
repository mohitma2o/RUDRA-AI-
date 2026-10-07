import sys
import unittest
from pathlib import Path

RUDRA_DIR = Path(__file__).parents[1] / "rudra"
sys.path.insert(0, str(RUDRA_DIR))

from main import detect_language
from tts import _choose_voice


class LanguageFlowTests(unittest.TestCase):
    def test_hindi_and_punjabi_are_distinct_and_wired_to_tts(self):
        hindi = detect_language("मैं आपकी मदद कैसे कर सकता हूँ")
        punjabi = detect_language("ਕੁਣ ਕੀਤੀ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ")

        self.assertEqual(hindi, "hi")
        self.assertEqual(punjabi, "pa")
        self.assertEqual(_choose_voice(hindi), "hi-IN-MadhurNeural")
        self.assertEqual(_choose_voice(punjabi), "pa-IN-AmanNeural")


if __name__ == "__main__":
    unittest.main()
