from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    QTimer,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from qfluentwidgets import FlowLayout


class WaterfallLayout(FlowLayout):
    """
    A Waterfall (Pinterest-like) layout with multiple columns of equal width
    but varying height.
    """

    def __init__(
        self,
        parent=None,
        default_col_width: int = 240,
        needAni: bool = False,
        isTight: bool = False,
    ):
        """
        Parameters
        ----------
        parent:
            parent window or layout

        needAni: bool
            whether to add moving animation

        isTight: bool
            whether to use the tight layout when widgets are hidden
        """
        super().__init__(parent)
        self._items = []
        self._anis = []
        self._aniGroup = QParallelAnimationGroup(self)

        self._verticalSpacing = 10
        self._horizontalSpacing = 10
        self.duration = 300
        self.ease = QEasingCurve.Type.Linear

        self.needAni = needAni
        self.isTight = isTight
        self._layouting = False

        # Debounce timer for layout updates
        self._deBounceTimer = QTimer(self)
        self._deBounceTimer.setSingleShot(True)
        self._deBounceTimer.timeout.connect(
            lambda: self._doLayout(self.geometry(), True)
        )

        self._wParent = None
        self._isInstalledEventFilter = False

        # Optional: If you’d like a fixed column count, set it here (>= 1).
        # Zero or negative means "auto-compute" based on widget width.
        self._fixedColumnCount = 0
        # You can also store a default column width if desired:
        self._defaultColumnWidth = default_col_width
        self._minColumnCount = 1

    def _onWidgetAdded(self, w, index=-1):
        if not self._isInstalledEventFilter:
            if w.parent():
                self._wParent = w.parent()
                w.parent().installEventFilter(self)
            else:
                w.installEventFilter(self)

        if not self.needAni:
            return

        # Create a QGraphicsOpacityEffect for the widget
        opacity_effect = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(opacity_effect)

        # Create a QPropertyAnimation for the opacity property
        ani = QPropertyAnimation(opacity_effect, b"opacity")
        ani.setStartValue(0)  # Start fully transparent
        ani.setEndValue(1)  # End fully opaque
        ani.setDuration(self.duration)
        ani.setEasingCurve(self.ease)

        # Disable the opacity effect after the animation finishes
        ani.finished.connect(lambda: w.setGraphicsEffect(None))

        w.setProperty("waterfallAni", ani)
        self._aniGroup.addAnimation(ani)

        # Force the widget to repaint
        w.update()

        if index == -1:
            self._anis.append(ani)
        else:
            self._anis.insert(index, ani)

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            item = self._items[index]
            ani = item.widget().property("waterfallAni")
            if ani:
                self._anis.remove(ani)
                self._aniGroup.removeAnimation(ani)
                ani.deleteLater()
            return self._items.pop(index).widget()
        return None

    def _doLayout(self, rect: QRect, move: bool):
        if not self._items:
            return 0

        margin = self.contentsMargins()
        left = rect.x() + margin.left()
        top = rect.y() + margin.top()
        availableWidth = rect.width() - margin.left() - margin.right()

        # Calculate number of columns and width
        spaceX = self._horizontalSpacing
        columnCount = max(
            self._minColumnCount,
            (availableWidth + spaceX) // (self._defaultColumnWidth + spaceX),
        )
        columnWidth = (availableWidth - (columnCount - 1) * spaceX) // columnCount
        columnHeights = [top] * columnCount

        # Simple single-pass layout
        for i, item in enumerate(self._items):
            if item.widget() and not item.widget().isVisible() and self.isTight:
                continue

            # Find shortest column
            col = columnHeights.index(min(columnHeights))

            # Calculate position
            x = left + col * (columnWidth + spaceX)
            y = columnHeights[col]

            # Calculate target geometry
            itemSize = item.sizeHint()
            scaledHeight = (
                int(itemSize.height() * (columnWidth / itemSize.width()))
                if itemSize.width() > 0
                else itemSize.height()
            )
            target = QRect(QPoint(x, y), QSize(columnWidth, scaledHeight))

            # Update widget geometry
            if move:
                if not self.needAni:
                    item.setGeometry(target)
                elif target != item.geometry():
                    item.setGeometry(target)
                    if self.needAni:
                        ani = item.widget().property("waterfallAni")
                        if ani:
                            ani.start()

            # Update column height
            columnHeights[col] = y + scaledHeight + self._verticalSpacing

        return max(columnHeights) + margin.bottom() - rect.y()
