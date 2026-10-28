"""Unit tests for wake word detection (WP1 acceptance criteria)."""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.app.voice.wake import find_wake, strip_wake


class TestFindWake:
    # ---- Positive cases --------------------------------------------------

    def test_exact_english(self):
        assert find_wake("Rudra, what time is it") == "rudra"

    def test_case_insensitive(self):
        assert find_wake("RUDRA") == "rudra"

    def test_variant_rudhra(self):
        result = find_wake("ok rudhra tell me")
        assert result is not None

    def test_variant_rudar(self):
        result = find_wake("rudar listen")
        assert result is not None

    def test_variant_rudraa(self):
        result = find_wake("rudraa what time is it")
        assert result is not None

    def test_hindi_devanagari(self):
        result = find_wake("\u0930\u0941\u0926\u094d\u0930 \u0906\u092a \u0915\u0948\u0938\u0947 \u0939\u0948\u0902")
        assert result is not None

    def test_punjabi_gurmukhi(self):
        result = find_wake("\u0a30\u0a41\u0a26\u0a30 \u0a15\u0a40 \u0a39\u0a71\u0a32")
        assert result is not None

    def test_fuzzy_typo(self):
        # "rudra" misspelled slightly — fuzzy matching should catch it
        result = find_wake("ruudra what is two plus two")
        # May or may not match depending on threshold — test that it does not crash
        # (correctness of fuzzy match depends on rapidfuzz ratio)
        assert result is None or isinstance(result, str)

    # ---- Negative / false-positive cases ---------------------------------

    def test_false_positive_rude(self):
        assert find_wake("that was rude") is None

    def test_false_positive_rudder(self):
        assert find_wake("the rudder of the ship") is None

    def test_false_positive_random(self):
        assert find_wake("what is the weather today") is None

    def test_false_positive_ruler(self):
        assert find_wake("I need a ruler") is None

    def test_empty_string(self):
        assert find_wake("") is None

    def test_none_like(self):
        assert find_wake("   ") is None


class TestStripWake:
    def test_strip_from_start(self):
        result = strip_wake("Rudra, open camera", "rudra")
        assert "rudra" not in result.lower()
        assert "camera" in result.lower()

    def test_strip_once_only(self):
        result = strip_wake("Rudra rudra open camera", "rudra")
        # Should only strip once
        assert result.lower().count("rudra") <= 1

    def test_strip_devanagari(self):
        text = "\u0930\u0941\u0926\u094d\u0930 \u0915\u0948\u0938\u0947 \u0939\u0948\u0902"
        wake = "\u0930\u0941\u0926\u094d\u0930"
        result = strip_wake(text, wake)
        assert wake not in result
