import unittest

from rudra.agent import detect_tool_call
from rudra.skills.system import APP_COMMAND_MAP


class AgentToolDispatchTests(unittest.TestCase):
    def test_detect_open_application(self):
        action = detect_tool_call("open notepad on my computer")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")
        self.assertIn("notepad", action["args"]["name"].lower())

    def test_detect_windows_command_aliases(self):
        self.assertIsNotNone(detect_tool_call("open calculator"))
        self.assertIsNotNone(detect_tool_call("open the terminal"))
        self.assertIsNotNone(detect_tool_call("open file explorer"))

    def test_windows_app_map_uses_real_commands(self):
        self.assertEqual(APP_COMMAND_MAP["calculator"], "calc")
        self.assertEqual(APP_COMMAND_MAP["terminal"], "wt")
        self.assertEqual(APP_COMMAND_MAP["file explorer"], "explorer")

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
