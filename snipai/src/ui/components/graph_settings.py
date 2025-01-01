from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QVBoxLayout
from qfluentwidgets import (
    CaptionLabel,
    SimpleCardWidget,
    Slider,
    SubtitleLabel,
)


class GraphSettingsPanel(SimpleCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)  # Set a fixed width for the panel
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Create an expand layout for organized sections
        self.expand_layout = QVBoxLayout(self)

        # Initialize both settings sections
        self._init_display_settings()
        self._init_force_settings()

        # Apply some styling
        self.setObjectName("settingsPanel")
        self.setStyleSheet("""
            #settingsPanel {
                background-color: rgb(251, 251, 251);
                border-left: 1px solid rgb(229, 229, 229);
            }
        """)

        # Schedule the positioning for after the widget is fully initialized
        QTimer.singleShot(0, self.move_to_bottom_right)

    def move_to_bottom_right(self):
        if self.parent():
            parent_rect = self.parent().rect()
            x = parent_rect.width() - self.width() - 20
            y = parent_rect.height() - self.height() - 20
            self.move(x, y)

    def _init_display_settings(self):
        # Create a container for display settings
        display_section = SimpleCardWidget(self)
        display_layout = QVBoxLayout(display_section)

        # Add section title
        display_title = SubtitleLabel("Display", display_section)
        display_layout.addWidget(display_title)

        # Create scale slider
        self.scale_slider = Slider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(50, 1000)  # Min and max scale values
        self.scale_slider.setValue(200)  # Default scale value
        self.scale_slider.setToolTip(
            "Adjust the overall size of the graph visualization"
        )
        scale_desc = CaptionLabel("Zoom level", display_section)
        display_layout.addWidget(scale_desc)
        display_layout.addWidget(self.scale_slider)

        # Add to main layout
        self.expand_layout.addWidget(display_section)

    def _init_force_settings(self):
        # Create a container for force settings
        force_section = SimpleCardWidget(self)
        force_layout = QVBoxLayout(force_section)

        # Add section title
        force_title = SubtitleLabel("Forces", force_section)
        force_layout.addWidget(force_title)

        # Create sliders for different force parameters
        self.k_slider = Slider(Qt.Orientation.Horizontal)
        self.k_slider.setRange(50, 500)
        self.k_slider.setValue(200)
        self.k_slider.setToolTip(
            "Controls the preferred distance between nodes"
        )
        self.k_desc = CaptionLabel("Distance between nodes", force_section)
        force_layout.addWidget(self.k_desc)
        force_layout.addWidget(self.k_slider)

        self.iterations_slider = Slider(Qt.Orientation.Horizontal)
        self.iterations_slider.setRange(10, 200)
        self.iterations_slider.setValue(50)
        self.iterations_slider.setToolTip(
            "Number of iterations for layout optimization"
        )
        self.iterations_desc = CaptionLabel("Iterations", force_section)
        force_layout.addWidget(self.iterations_desc)
        force_layout.addWidget(self.iterations_slider)

        # Add to main layout
        self.expand_layout.addWidget(force_section)
