"""
RUDRA AI - Wake Word Listener Service
Background audio listener that listens for the keyword "Rudra" or "Hey Rudra".
When detected, it signals the application to bring the window to the foreground.
"""

import threading
import time
import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)

class WakeWordService:
    """Service that runs a background listener for the wake word 'Rudra'."""

    def __init__(self):
        self.is_listening = False
        self._thread = None
        self.wake_word = "rudra"
        self.callbacks = []

    def register_callback(self, callback):
        """Register a function to call when wake word is detected."""
        self.callbacks.append(callback)

    def start_listening(self):
        """Start the background wake word listener thread."""
        if self.is_listening:
            return
        self.is_listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word listener started for keyword '%s'", self.wake_word)

    def stop_listening(self):
        """Stop the listener thread."""
        self.is_listening = False
        logger.info("Wake word listener stopped")

    def _trigger_wake(self):
        """Called when 'Rudra' is detected."""
        logger.info("⚡ WAKE WORD DETECTED: 'Rudra'!")
        for cb in self.callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("Error in wake callback: %s", e)

    def _listen_loop(self):
        """Background thread loop listening for wake word."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            # Dynamic energy thresholding for background noise adaptation
            recognizer.dynamic_energy_threshold = True
            recognizer.energy_threshold = 300

            mic = sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)

            logger.info("Microphone initialized for Wake Word detection.")

            while self.is_listening:
                try:
                    with mic as source:
                        # Listen for short phrase (phrase_time_limit=3s)
                        audio = recognizer.listen(source, timeout=2.0, phrase_time_limit=3.0)

                    # Recognize using online/offline Google STT or local sphinx
                    try:
                        text = recognizer.recognize_google(audio).lower()
                        logger.debug("Heard audio: '%s'", text)

                        if self.wake_word in text or "rudra" in text or "ruder" in text or "rudhra" in text:
                            self._trigger_wake()
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        logger.warning("Wake word recognition network error: %s", e)

                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logger.error("Wake word loop error: %s", e)
                    time.sleep(1)

        except ImportError:
            logger.warning(
                "SpeechRecognition package not installed. Installing optional voice deps. "
                "Wake word detection will fall back to manual API trigger."
            )
            while self.is_listening:
                time.sleep(2)


# Global service instance
wake_word_service = WakeWordService()
