from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from qfluentwidgets import CheckableMenu, ComboBox, MenuIndicatorType


class MultiSelectionComboBox(ComboBox):
    """
    A ComboBox that allows selecting multiple items at once
    """

    selectionChanged = pyqtSignal(list)  # Emits a list of checked ComboItem objects

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._checked_indexes = []  # Track selected indices
        self._placeholderText = "Select items..."
        self.setText(self._placeholderText)
        self._updateTextState(True)

    def _createComboMenu(self):
        """Create a checkable menu for multi-selection"""
        menu = CheckableMenu(
            title="", parent=self, indicatorType=MenuIndicatorType.CHECK
        )
        menu.setItemHeight(33)

        for i, item in enumerate(self.items):
            action = QAction(item.text, menu)
            action.setCheckable(True)
            action.setEnabled(item.isEnabled)
            if item.icon:
                action.setIcon(item.icon)
            action.setChecked(i in self._checked_indexes)
            action.toggled.connect(
                lambda checked, idx=i, act=action: self._onItemToggled(idx, act)
            )
            menu.addAction(action)

        if menu.view.width() < self.width():
            menu.view.setMinimumWidth(self.width())
            menu.adjustSize()

        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.closedSignal.connect(self._onDropMenuClosed)
        return menu

    def _showComboMenu(self):
        """Override to handle multi-selection menu display"""
        if not self.items:
            return

        menu = self._createComboMenu()  # This creates our CheckableMenu with actions

        # Set menu display properties
        if menu.view.width() < self.width():
            menu.view.setMinimumWidth(self.width())
            menu.adjustSize()

        menu.setMaxVisibleItems(self.maxVisibleItems())
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.closedSignal.connect(self._onDropMenuClosed)
        self.dropMenu = menu

        # Position and show the menu
        x = (
            -menu.width() // 2
            + menu.layout().contentsMargins().left()
            + self.width() // 2
        )
        pd = self.mapToGlobal(QPoint(x, self.height()))
        menu.exec(pd)

    def _onItemToggled(self, index: int, action: QAction):
        """Handle item toggle events"""
        if action.isChecked():
            if index not in self._checked_indexes:
                self._checked_indexes.append(index)
        else:
            if index in self._checked_indexes:
                self._checked_indexes.remove(index)

        self._checked_indexes.sort()

        # Update display text
        if self._checked_indexes:
            selected_texts = []
            for i in self._checked_indexes:
                if 0 <= i < len(self.items):
                    selected_texts.append(self.items[i].text)
            self.setText(", ".join(selected_texts))
            self._updateTextState(False)
        else:
            self.setText(self._placeholderText)
            self._updateTextState(True)

        self.selectionChanged.emit([item.text for item in self.checkedItems()])

    def checkedItems(self):
        """Get list of selected items"""
        return [self.items[i] for i in self._checked_indexes]

    def checkedIndexes(self):
        """Get list of selected indices"""
        return self._checked_indexes[:]

    def clearChecks(self):
        """Clear all selections"""
        self._checked_indexes.clear()
        self.setText(self._placeholderText)
        self._updateTextState(True)
        self.selectionChanged.emit([])

    def setCheckedIndexes(self, indexes: list[int]):
        """Set selected indices"""
        valid = [i for i in indexes if 0 <= i < len(self.items)]
        self._checked_indexes = list(set(valid))

        if self._checked_indexes:
            selected_texts = [self.items[i].text for i in sorted(self._checked_indexes)]
            self.setText(", ".join(selected_texts))
            self._updateTextState(False)
        else:
            self.setText(self._placeholderText)
            self._updateTextState(True)

        self.selectionChanged.emit([item.text for item in self.checkedItems()])

    def setPlaceholderText(self, text: str):
        """Set placeholder text shown when no items are selected"""
        self._placeholderText = text
        if not self._checked_indexes:
            self.setText(text)
            self._updateTextState(True)
