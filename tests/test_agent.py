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

    # ── File-open spoken phrase tests ──────────────────────────────

    def test_open_my_resume_captures_full_phrase(self):
        """'open my resume' should route to open_file with name='resume'."""
        action = detect_tool_call("open my resume")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_file")
        self.assertIn("resume", action["args"]["name"].lower())
        # Should NOT have "my" left in the name
        self.assertNotIn("my", action["args"]["name"].lower().split())

    def test_open_multiword_filename(self):
        """'open project proposal' should capture the full multi-word name."""
        action = detect_tool_call("open project proposal")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_file")
        self.assertIn("project proposal", action["args"]["name"].lower())

    def test_open_file_strips_filler(self):
        """'open my document budget please' should strip 'my', 'document', 'please'."""
        action = detect_tool_call("open my document budget please")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_file")
        self.assertIn("budget", action["args"]["name"].lower())

    def test_open_file_does_not_return_path(self):
        """The open_file args should only have 'name', not 'path'."""
        action = detect_tool_call("open my resume")
        self.assertIsNotNone(action)
        self.assertNotIn("path", action["args"])

    def test_app_takes_precedence_over_file(self):
        """'open notepad' should match the app, not the file handler."""
        action = detect_tool_call("open notepad")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")


if __name__ == "__main__":
    unittest.main()
