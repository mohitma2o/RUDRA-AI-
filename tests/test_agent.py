import unittest
import tempfile
from pathlib import Path

from rudra.agent import _execute_tool_action, detect_tool_call
from rudra.llm import SYSTEM_PROMPT, TOOL_SCHEMAS
from rudra.skills.files import MAX_DOCUMENT_TEXT_CHARS, read_document
from rudra.skills.system import APP_COMMAND_MAP, _match_app_in_list
from rudra.wakeword import _select_wakeword_trigger


class AgentToolDispatchTests(unittest.TestCase):
    def test_casual_check_in_prompt_is_short_and_human(self):
        self.assertIn("you alive?", SYSTEM_PROMPT.lower())
        self.assertIn("Alive and kicking", SYSTEM_PROMPT)
        self.assertIn("Right here", SYSTEM_PROMPT)

    def test_capture_photo_tool_description_accepts_click_phrases(self):
        capture_schema = next(
            schema["function"] for schema in TOOL_SCHEMAS if schema["function"]["name"] == "capture_photo"
        )
        self.assertIn("click a picture", capture_schema["description"].lower())
        self.assertIn("click an image", capture_schema["description"].lower())
        self.assertIn("click a photo", capture_schema["description"].lower())

    def test_detect_open_application(self):
        action = detect_tool_call("open notepad on my computer")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")
        self.assertIn("notepad", action["args"]["name"].lower())

    def test_detect_windows_command_aliases(self):
        self.assertIsNotNone(detect_tool_call("open calculator"))
        self.assertIsNotNone(detect_tool_call("open the terminal"))
        self.assertIsNotNone(detect_tool_call("open file explorer"))

    def test_open_camera_routes_to_camera_application(self):
        action = detect_tool_call("open camera")
        self.assertEqual(action["tool"], "open_application")
        self.assertEqual(action["args"]["name"], "camera")

    def test_installed_app_match_is_case_insensitive_and_fuzzy(self):
        apps = [{"Name": "Camera", "AppID": "camera-id"}]
        self.assertEqual(_match_app_in_list("CAMERA", apps), apps[0])
        self.assertEqual(_match_app_in_list("camer", apps), apps[0])
        self.assertIsNone(_match_app_in_list("unrelated", apps))

    def test_windows_app_map_uses_real_commands(self):
        self.assertEqual(APP_COMMAND_MAP["calculator"], "calc")
        self.assertEqual(APP_COMMAND_MAP["terminal"], "wt")
        self.assertEqual(APP_COMMAND_MAP["file explorer"], "explorer")

    def test_indexed_apps_do_not_bypass_dynamic_resolution(self):
        for app in ("chrome", "google chrome", "edge", "word", "excel", "spotify"):
            self.assertNotIn(app, APP_COMMAND_MAP)

    def test_open_application_failure_does_not_say_done(self):
        from unittest.mock import patch

        with patch("rudra.agent.open_application", return_value="Failed to open 'chrome'. Application did not start."):
            result = self._run_execute_tool_call("open chrome")
            self.assertNotIn("Done", result)
            self.assertEqual(result, "Failed to open 'chrome'. Application did not start.")

    def test_open_application_direct_failure(self):
        from rudra.skills.system import open_application

        res = open_application("nonexistent_app_xyz", timeout=0.1)
        self.assertIn("Failed to open", res)

    def test_open_application_success_says_done(self):
        from unittest.mock import patch

        with patch("rudra.agent.open_application", return_value="Opening notepad now."):
            result = self._run_execute_tool_call("open notepad")
            self.assertEqual(result, "Done — Opening notepad now.")

    def test_detect_search_file_action(self):
        action = detect_tool_call("search for my report in documents folder")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "search_file")
        self.assertIn("report", action["args"]["name"].lower())

    def test_detect_new_voice_commands(self):
        expected = {
            "take a picture": "capture_photo",
            "take a photo": "capture_photo",
            "take a picture and search for it": "capture_photo",
            "email test@example.com": "compose_email",
            "send an email to test@example.com": "compose_email",
            "open my downloads folder": "open_folder",
            "open downloads": "open_folder",
            "what's on my screen": "read_screen",
            "read my screen": "read_screen",
            "read this page": "read_screen",
            "what does README.md say": "read_document",
            "summarize README.md": "read_document",
            "read me README.md": "read_document",
        }
        for command, tool in expected.items():
            with self.subTest(command=command):
                self.assertEqual(detect_tool_call(command)["tool"], tool)

    def test_email_command_passes_recipient_to_mail_draft(self):
        from unittest.mock import patch

        with patch("rudra.agent.compose_email", return_value="Opened URL: mailto:test@example.com") as compose:
            result = self._run_execute_tool_call("email test@example.com")
        compose.assert_called_once_with("test@example.com", subject="", body="")
        self.assertIn("mailto:test@example.com", result)

    def test_compose_email_forwards_subject_and_body(self):
        from unittest.mock import patch

        with patch("rudra.agent.compose_email", return_value="Opened URL: mailto:john@example.com") as compose:
            result = _execute_tool_action(
                "compose_email",
                {"to": "john@example.com", "subject": "Late", "body": "I'll be 10 minutes late."},
            )
        compose.assert_called_once_with("john@example.com", subject="Late", body="I'll be 10 minutes late.")
        self.assertIn("mailto:john@example.com", result)

    def test_folder_command_opens_resolved_shortcut(self):
        from unittest.mock import patch

        with patch("rudra.agent.open_folder", return_value="Opened folder: Downloads") as opener:
            result = self._run_execute_tool_call("open my downloads folder")
        opener.assert_called_once_with("downloads")
        self.assertEqual(result, "Done — Opened folder: Downloads")

    def test_camera_reverse_search_requires_a_real_capture(self):
        from unittest.mock import patch

        with patch("rudra.agent.capture_photo", return_value="Unable to open webcam."), patch(
            "rudra.agent.reverse_image_search"
        ) as reverse_search:
            result = self._run_execute_tool_call("take a picture and search for it")
        self.assertEqual(result, "Unable to open webcam.")
        reverse_search.assert_not_called()

    def test_screen_text_is_summarized_with_length_cap(self):
        from unittest.mock import patch

        received = []

        def summarize(prompt):
            received.append(prompt)
            return "A concise screen summary."

        with patch("rudra.agent.read_screen", return_value="x" * 5000):
            result = self._run_execute_tool_call("what's on my screen", llm_fn=summarize)
        extracted_text = received[0].split("screen text:\n", 1)[1]
        self.assertLessEqual(len(extracted_text), 3000)
        self.assertEqual(result, "Done — A concise screen summary.")

    def test_document_is_found_read_and_summarized(self):
        from unittest.mock import patch

        with patch("rudra.agent._resolve_open_file_target", return_value=("notes", ["notes.md"], "notes")), patch(
            "rudra.agent.read_document", return_value="The document content."
        ) as read, patch("rudra.agent._summarize_extracted_text", return_value="Done — Summary") as summarize:
            result = self._run_execute_tool_call("summarize notes")
        read.assert_called_once_with("notes.md")
        summarize.assert_called_once_with("The document content.", "document", None)
        self.assertEqual(result, "Done — Summary")

    def test_document_extraction_is_capped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.txt"
            path.write_text("x" * (MAX_DOCUMENT_TEXT_CHARS + 100), encoding="utf-8")
            text = read_document(str(path))
        self.assertLessEqual(len(text), MAX_DOCUMENT_TEXT_CHARS)
        self.assertTrue(text.endswith("[Text truncated.]"))

    def test_general_question_has_no_action(self):
        action = detect_tool_call("what is the capital of France?")
        self.assertIsNone(action)

    def test_wakeword_trigger_uses_reliable_threshold(self):
        predictions = {"rudra": 0.48, "noise": 0.13}
        self.assertEqual(_select_wakeword_trigger(predictions, threshold=0.45), "rudra")
        self.assertIsNone(_select_wakeword_trigger({"noise": 0.13}, threshold=0.45))

    def test_novel_phrases_are_not_regex_dispatches(self):
        for phrase in (
            "can you pull up chrome for me",
            "I need to see what's going on with my downloads folder",
            "snap a photo",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(detect_tool_call(phrase))

    def test_tool_call_response_executes_and_sends_result_for_followup(self):
        from unittest.mock import patch
        from rudra.agent import agent_response

        model_message = {
            "content": "",
            "tool_calls": [{"function": {"name": "open_application", "arguments": {"name": "Chrome"}}}],
        }
        calls = []
        with patch("rudra.agent.open_application", return_value="Opening Chrome now."):
            result = agent_response(
                "can you pull up chrome for me",
                lambda prompt: "fallback",
                tool_call_fn=lambda prompt: {"message": model_message},
                tool_followup_fn=lambda message, tool_messages: calls.extend(tool_messages) or "Chrome is open.",
            )
        self.assertEqual(result, "Chrome is open.")
        self.assertEqual(calls, [{"role": "tool", "content": "Done — Opening Chrome now."}])

    def test_regex_dispatch_remains_fallback_when_model_returns_plain_text(self):
        from unittest.mock import patch
        from rudra.agent import agent_response

        plain_response = {"message": {"content": "I will open the Camera app.", "tool_calls": []}}
        with patch("rudra.agent.open_application", return_value="Opening Camera now."):
            result = agent_response(
                "open camera",
                lambda prompt: "fallback response",
                tool_call_fn=lambda prompt: plain_response,
            )

        self.assertEqual(result, "Done — Opening Camera now.")

    def test_failed_tool_followup_does_not_repeat_action(self):
        from unittest.mock import patch
        from rudra.agent import agent_response

        model_response = {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "open_application", "arguments": {"name": "Camera"}}}],
            }
        }
        with patch("rudra.agent.open_application", return_value="Opening Camera now.") as open_app:
            result = agent_response(
                "open camera",
                lambda prompt: "fallback",
                tool_call_fn=lambda prompt: model_response,
                tool_followup_fn=lambda message, tool_messages: (_ for _ in ()).throw(RuntimeError("Ollama stopped")),
            )

        self.assertEqual(open_app.call_count, 1)
        self.assertIn("Opening Camera now.", result)

    def test_camera_capture_tries_three_indices_and_reports_windows_setting(self):
        from unittest.mock import Mock, patch
        from rudra.skills.vision import capture_photo

        cameras = []

        def video_capture(index):
            camera = Mock()
            camera.isOpened.return_value = False
            cameras.append(index)
            return camera

        with patch("cv2.VideoCapture", side_effect=video_capture), patch("cv2.imwrite"):
            result = capture_photo()

        self.assertEqual(cameras, [0, 1, 2])
        self.assertIn('"Let desktop apps access your camera"', result)
        self.assertIn("OpenCV emitted no native diagnostic", result)

    # ── File-open spoken phrase tests ──────────────────────────────

    def test_open_my_resume_captures_full_phrase(self):
        """Generic open phrases try app resolution before file search."""
        action = detect_tool_call("open my resume")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")
        self.assertIn("resume", action["args"]["name"].lower())
        # Should NOT have "my" left in the name
        self.assertNotIn("my", action["args"]["name"].lower().split())

    def test_open_multiword_filename(self):
        """'open project proposal' should capture the full multi-word name."""
        action = detect_tool_call("open project proposal")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")
        self.assertIn("project proposal", action["args"]["name"].lower())

    def test_open_file_strips_filler(self):
        """'open my document budget please' should strip 'my', 'document', 'please'."""
        action = detect_tool_call("open file my document budget please")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_file")
        self.assertIn("budget", action["args"]["name"].lower())

    def test_open_file_does_not_return_path(self):
        """The open_file args should only have 'name', not 'path'."""
        action = detect_tool_call("open file my resume")
        self.assertIsNotNone(action)
        self.assertNotIn("path", action["args"])

    def test_open_file_missing_match_speaks_clear_not_found(self):
        """A missing file should speak a friendly message rather than a raw path error."""
        from unittest.mock import patch

        with patch("rudra.agent.open_application", return_value="Failed to open 'does not exist anywhere here'. Application not found."), patch(
            "rudra.agent.search_file", return_value=[]
        ):
            result = self._run_execute_tool_call("open does not exist anywhere here")
        self.assertIn("I couldn't find a file matching", result)
        self.assertNotIn("File not found:", result)

    def test_app_takes_precedence_over_file(self):
        """'open notepad' should match the app, not the file handler."""
        action = detect_tool_call("open notepad")
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "open_application")

    def test_open_falls_back_to_file_when_no_app_match(self):
        from unittest.mock import patch

        with patch("rudra.agent.open_application", return_value="Failed to open 'resume'. Application not found."), patch(
            "rudra.agent.search_file", return_value=[]
        ):
            result = self._run_execute_tool_call("open resume")
        self.assertIn("I couldn't find a file matching 'resume'", result)

    @staticmethod
    def _run_execute_tool_call(prompt: str, llm_fn=None) -> str:
        from rudra.agent import execute_tool_call
        return execute_tool_call(prompt, llm_fn=llm_fn)


if __name__ == "__main__":
    unittest.main()
