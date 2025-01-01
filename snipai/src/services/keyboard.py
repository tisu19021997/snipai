# File: keyboard.py

from typing import Dict, Set, Optional
from pydantic import BaseModel
from loguru import logger
from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal


class Hotkey(BaseModel):
    keys: Set[str]

    class Config:
        arbitrary_types_allowed = True


class KeyboardService(QObject):
    hotkey_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_keys: Set[str] = set()
        self._registered_hotkeys: Dict[str, Hotkey] = {}
        self._listener = None
        self._setup_listener()

    def _setup_listener(self):
        """Setup the keyboard listener"""
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False,  # Don't suppress events
            )
            self._listener.start()
            logger.info("Global keyboard listener started")
        except Exception as e:
            logger.error(f"Failed to setup keyboard listener: {e}")

    def register_hotkey(self, keys: Set[str], action_key: str) -> None:
        """Register a new hotkey combination"""
        if not any(keys):
            return
        # Normalize key names
        normalized_keys = {k.lower() for k in keys}
        hotkey = Hotkey(keys=normalized_keys)
        self._registered_hotkeys[action_key] = hotkey
        logger.info(f"Registered hotkey {normalized_keys} for action {action_key}")

    def _get_key_name(self, key: keyboard.Key) -> Optional[str]:
        """Convert a pynput key to a standardized string name"""
        try:
            if key is None:
                logger.debug("Received None key")
                return None

            # Handle special keys
            if isinstance(key, keyboard.Key):
                return key.name.lower()
            # Handle character keys
            if hasattr(key, "char") and key.char is not None:
                return key.char.lower()
            # Handle other keys that might have a name attribute
            if hasattr(key, "name") and key.name is not None:
                return key.name.lower()
            return None
        except Exception as e:
            logger.warning(f"Unrecognized key: {e}")
            return None

    def _on_press(self, key: keyboard.Key) -> None:
        """Handle key press events"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                self._current_keys.add(key_name)
                self._check_hotkeys()
        except Exception as e:
            logger.error(f"Error in keyboard press handler: {e}")

    def _on_release(self, key: keyboard.Key) -> None:
        """Handle key release events"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                self._current_keys.discard(key_name)
        except Exception as e:
            logger.error(f"Error in keyboard release handler: {e}")

    def _check_hotkeys(self) -> None:
        """Check if any registered hotkeys match the current key combination"""
        for action_key, hotkey in self._registered_hotkeys.items():
            if hotkey.keys.issubset(self._current_keys):
                logger.info(f"Hotkey matched: {hotkey.keys} -> {action_key}")
                self.hotkey_triggered.emit(action_key)

    def reset(self) -> None:
        """Reset the keyboard service state"""
        self._current_keys.clear()

    def cleanup(self) -> None:
        """Clean up resources"""
        if self._listener:
            self._listener.stop()
