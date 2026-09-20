import unittest

from rudra.agent import detect_tool_call


class AgentToolDispatchTests(unittest.TestCase):
    def test_detect_open_application(self):
        action = detect_tool_call("open notepad on my computer")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")
        self.assertIn("notepad", action["args"]["name"].lower())

    def test_detect_search_file_action(self):
        action = detect_tool_call("search for my report in documents folder")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "search_file")
        self.assertIn("report", action["args"]["name"].lower())

    def test_general_question_has_no_action(self):
        action = detect_tool_call("what is the capital of France?")
        self.assertIsNone(action)


if __name__ == "__main__":
    unittest.main()
