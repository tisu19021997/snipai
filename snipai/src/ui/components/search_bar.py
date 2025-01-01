from PyQt6.QtCore import Qt
from qfluentwidgets import SearchLineEdit


class SnipSearchBar(SearchLineEdit):
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.search()
        else:
            super().keyPressEvent(event)
