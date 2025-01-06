from qfluentwidgets import ScrollArea
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from snipai.src.common.style_sheet import StyleSheet


class RecentInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWidget(self)
        self.main_layout = QVBoxLayout(self.view)

        self.__init_widget()

    def __init_widget(self):
        self.view.setObjectName("view")
        self.setObjectName("recent_interface")
        StyleSheet.HOME_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.main_layout.setContentsMargins(0, 0, 0, 36)
        self.main_layout.setSpacing(40)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
