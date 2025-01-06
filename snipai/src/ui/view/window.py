import sys
from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QWindowStateChangeEvent
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
)

from snipai.src.common.resources import paths
from snipai.src.services import KeyboardService, StorageService
from snipai.src.ui.components.snip import SelectionCompletedEvent, SnipWidget
from snipai.src.ui.view import BookmarksInterface, SettingInterface
from snipai.src.ui.view.home_interface import HomeInterface


class Window(FluentWindow):
    """Main Interface"""

    def __init__(self):
        super().__init__()

        self.init_services()
        self.init_navigation()
        self.init_window()
        self.init_widgets()

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.activateWindow()
        self.raise_()

    def init_navigation(self):
        self.addSubInterface(self.bookmarksInterface, FIF.PHOTO, "Your snips")
        self.addSubInterface(self.homeInterface, FIF.GLOBE, "Explore")
        self.navigationInterface.addSeparator()

        self.addSubInterface(
            self.settingInterface,
            FIF.SETTING,
            "Settings",
            NavigationItemPosition.BOTTOM,
        )

    def init_window(self):
        # self.resize(900, 700)
        self.setWindowIcon(QIcon(str(paths.LOGO / "logo.png")))
        self.setWindowTitle("snip.ai")

        # Set the window to fullscreen mode
        self.showMaximized()

        # Add these to improve window activation behavior
        # Keep window in taskbar/dock
        self.setWindowFlag(Qt.WindowType.Tool, False)

        # Ensure proper window activation behavior
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

        # Don't hide from taskbar/dock
        if sys.platform == "darwin":  # macOS specific
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)

    def init_services(self):
        # Storage service to save and load files
        self.storage_service = StorageService(paths.ASSET)
        self.storage_service.image_saved.connect(self._on_storage_image_saved)
        self.storage_service.error_occurred.connect(self._on_error_occured)

        self.homeInterface = HomeInterface(self.storage_service, parent=self)
        # Bookmarks interface to manage bookmarks
        self.bookmarksInterface = BookmarksInterface(self.storage_service, parent=self)

        self.settingInterface = SettingInterface(self.storage_service, self)

        self.keyboard_service = KeyboardService(self)
        self.keyboard_service.hotkey_triggered.connect(self._handle_hotkey)
        # Modifiable hotkeys
        for hotkey_setting in self.settingInterface.hotkey_settings:
            # Register default value.
            self._register_hotkey(hotkey_setting.value(), hotkey_setting.key)
            hotkey_setting.textChanged.connect(self._register_hotkey)
        # Immutable hotkeys
        self._register_hotkey("esc", action_key="snip_cancel")  # Cancel snip

    def init_widgets(self):
        self.snip_widget = SnipWidget()
        # On finish snipping, save the screenshot to storage service
        self.snip_widget.selection_completed.connect(self._on_selection_completed)

    def show_notification(
        self,
        level: Literal["success", "warning", "error", "info"],
        message: str,
        title: str,
        duration=2000,
    ):
        # Get screen geometry
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            pos = InfoBarPosition.TOP_RIGHT
        info_bar_fn = {
            "success": InfoBar.success,
            "warning": InfoBar.warning,
            "error": InfoBar.error,
            "info": InfoBar.info,
        }
        info_bar = info_bar_fn[level](
            content=message,
            title=title,
            parent=self,
            position=pos,
            duration=duration,
        )
        # Move the InfoBar to top of screen with some padding
        info_bar.move(screen_geometry.width() - info_bar.width() - 20, 20)
        info_bar.show()

    def _register_hotkey(self, hotkey: str, action_key: str):
        # TODO: validate hotkey
        keys = set(hotkey.split("+"))
        if not any(keys):
            self.show_notification("error", f"Hotkey can't be empty: {hotkey}", "Error")
            return

        self.keyboard_service.register_hotkey(keys, action_key=action_key)

    def _handle_hotkey(self, action_key: str):
        """Handle hotkey triggers on the main thread"""

        # Map action keys to their handlers
        actions = {
            "snip_start": self.snip_widget.prepare_drawing,
            "snip_cancel": self.snip_widget.cancel_drawing,
        }

        # Execute the appropriate handler
        if handler := actions.get(action_key):
            if action_key == "snip_start":
                self.setWindowOpacity(0)
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            else:
                self.setWindowOpacity(1)
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            handler()

    def _on_selection_completed(self, event: SelectionCompletedEvent):
        self.storage_service.save_screenshot(event.pixmap)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowOpacity(1)

        # Ensure window is visible and active
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_storage_image_saved(self, image_id: str):
        self.show_notification("info", f"Saved screenshot id {image_id}", "Screenshot")

    def _on_error_occured(self, error_message: str):
        self.show_notification(
            "error", f"Error saving screenshot: {error_message}", "Error"
        )

    def showEvent(self, event):
        """Override to ensure proper window restoration"""
        super().showEvent(event)
        # Ensure window is visible and properly activated
        self.setWindowOpacity(1)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

    def changeEvent(self, event):
        """Handle window state changes"""
        super().changeEvent(event)
        if event.type() == QWindowStateChangeEvent:
            # If window was minimized, ensure it can be restored
            if self.windowState() & Qt.WindowMinimized:
                self.setWindowOpacity(1)
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
