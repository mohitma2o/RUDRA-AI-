import unittest
from unittest.mock import patch

from rudra.agent import _execute_tool_action


class DebugScreenTests(unittest.TestCase):
    def test_debug_screen_uses_existing_ocr_and_debug_prompt(self):
        llm_calls = []

        def llm(prompt):
            llm_calls.append(prompt)
            return "Likely issue: the traceback was truncated."

        with patch("rudra.agent.read_screen", return_value="Traceback: ValueError: bad data") as read_screen:
            result = _execute_tool_action("debug_screen", {}, llm_fn=llm, prompt="help me debug this")

        read_screen.assert_called_once_with()
        self.assertIn("code/error text read from the user's screen", llm_calls[0])
        self.assertIn("Traceback: ValueError: bad data", llm_calls[0])
        self.assertIn("likely bugs", llm_calls[0])
        self.assertIn("Likely issue", result)


if __name__ == "__main__":
    unittest.main()
