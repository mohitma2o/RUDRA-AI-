import unittest
from unittest.mock import MagicMock, Mock, patch

import numpy as np

from rudra.skills.screen import read_screen


class ScreenCaptureTests(unittest.TestCase):
    def test_read_screen_uses_full_virtual_desktop(self):
        capture = MagicMock()
        capture.monitors = [Mock()]
        capture.grab.return_value = Mock(rgb=b"x" * 100, width=3200, height=1800)
        capture.__enter__.return_value = capture
        reader = Mock()
        reader.readtext.return_value = ["primary", "secondary"]

        image = np.zeros((1800, 3200, 3), dtype=np.uint8)
        with patch("mss.mss", return_value=capture), patch(
            "easyocr.Reader", return_value=reader
        ), patch("numpy.frombuffer", return_value=image), patch(
            "cv2.resize", side_effect=lambda image, size, interpolation: image
        ):
            result = read_screen()

        capture.grab.assert_called_once_with(capture.monitors[0])
        self.assertIn("primary", result)
        self.assertIn("secondary", result)


if __name__ == "__main__":
    unittest.main()
