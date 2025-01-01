from pydantic import BaseModel
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent, QPainter, QPixmap
from loguru import logger

from snipai.src.common.utils import euclidean_distance_qline as dline


class SelectionCompletedEvent(BaseModel):
    rect: QRectF
    pixmap: QPixmap

    class Config:
        arbitrary_types_allowed = True


class SnipWidget(QWidget):
    # Signals
    selection_completed = pyqtSignal(SelectionCompletedEvent)
    selection_cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._reset()
        self._last_pixmap = None
        self._setup_ui()

    def _reset(self):
        self._start_point: QPointF = None
        self._current_point: QPointF = None
        self._is_drawing: bool = False
        self._is_prepared: bool = False
        self.setMouseTracking(False)

    def _setup_ui(self):
        self.setParent(None)
        # Set minimal window flags initially
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()  # Hide initially

        # Get the geometry that encompasses all screens
        total_geometry = self._get_total_screen_geometry()
        self.setGeometry(total_geometry)
        self.setObjectName("snap_widget")

    def _get_total_screen_geometry(self):
        """Get the combined geometry of all screens"""
        desktop = QGuiApplication.primaryScreen()
        if not desktop:
            return QRectF()

        # Get all screens
        screens = QGuiApplication.screens()

        # Calculate the bounding rectangle that contains all screens
        total_geometry = screens[0].geometry()
        for screen in screens[1:]:
            total_geometry = total_geometry.united(screen.geometry())

        return total_geometry

    def prepare_drawing(self):
        if self._is_prepared or self._is_drawing:
            return

        logger.debug("Snip: preparing to draw")
        self.setCursor(Qt.CursorShape.CrossCursor)
        # Update window flags when preparing to draw
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        # Make it receive mouse events
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Cover entire screen
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())

        self._is_prepared = True
        self.show()  # Show the window
        self.raise_()  # Bring to front
        # self.activateWindow()  # Make it active

        # Force repaint
        self.update()

    def start_drawing(self):
        if self._is_drawing or not self._is_prepared:
            return

        logger.debug(f"Snip: drawing")

        self.setMouseTracking(True)
        mouse_pos = self._locate_mouse_pos()
        self._start_point = mouse_pos
        self._current_point = mouse_pos
        self._is_drawing = True
        self._is_prepared = False
        self._last_pixmap = None

        self.update()

    def stop_drawing(self):
        if not self._is_drawing:
            return

        self.setCursor(Qt.CursorShape.ArrowCursor)

        if self._start_point and self._current_point:
            if dline(self._start_point, self._current_point) <= 32:
                self.cancel_drawing()
                return

            # First hide the overlay window temporarily
            bounds = self._calculate_bounds()
            self.hide()
            # Use a small delay to ensure the window is fully hidden
            QTimer.singleShot(50, lambda: self._capture_area(bounds))
        self.update()

    def cancel_drawing(self):
        self._reset()
        self.hide()
        self.selection_cancelled.emit()
        self.update()

    def _capture_area(self, bounds: QRectF):
        screen = QGuiApplication.primaryScreen()
        pixmap = screen.grabWindow(
            0,
            int(bounds.x()),
            int(bounds.y()),
            int(bounds.width()),
            int(bounds.height()),
        )
        self.selection_completed.emit(
            SelectionCompletedEvent(rect=bounds, pixmap=pixmap)
        )
        self._last_pixmap = pixmap
        self._reset()

    def _locate_mouse_pos(self):
        # Get current cursor position in global coordinates
        global_pos = QCursor.pos()
        # Convert global position to widget coordinates
        local_pos = self.mapFromGlobal(global_pos)
        return QPointF(local_pos)

    def _dist(self, point1: QPointF, point2: QPointF) -> float:
        """Calculates Euclidean distance using QLineF"""
        line = QLineF(point1, point2)
        return line.length()

    def _calculate_bounds(self) -> QRectF:
        """Calculate the bounding rectangle of the selection"""
        if not self._start_point or not self._current_point:
            return QRectF()

        x1, y1 = self._start_point.x(), self._start_point.y()
        x2, y2 = self._current_point.x(), self._current_point.y()

        # Calculate top-left and dimensions, handling any direction of drag
        x = min(x1, x2)
        y = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)

        return QRectF(x, y, width, height)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement during drawing"""
        if self._is_drawing and self._start_point:
            self._current_point = event.position()
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        logger.debug(f"Mouse pressed: {event.button()}")
        if event.button() == Qt.MouseButton.LeftButton and self._is_prepared:
            self.start_drawing()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_drawing:
            self.stop_drawing()

    def paintEvent(self, event) -> None:
        """Draw the selection rectangle with internal gray overlay"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_prepared:
            # Fill with very slightly visible background when prepared
            painter.fillRect(
                self.rect(), QColor(128, 128, 128, 1)
            )  # Almost transparent gray
            return

        if not self._is_drawing and not self._last_pixmap:
            # Clear any existing overlay
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
            return

        if (
            not (self._is_drawing or self._last_pixmap)
            or not self._start_point
            or not self._current_point
        ):
            return

        # Start with a completely transparent widget
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        # Switch back to normal composition mode
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Calculate bounds
        bounds = self._calculate_bounds()

        # Add semi-transparent gray overlay inside the selection bounds
        overlay = QColor(128, 128, 128, 100)  # Gray with 100/255 alpha
        painter.fillRect(bounds, overlay)
