import math
import os
from typing import Any, Callable, Tuple

import networkx as nx
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from snipai.src.common.config import cfg


class ClusterNode(QGraphicsObject):
    clicked = pyqtSignal(str)

    def __init__(self, tag, count, parent=None):
        super().__init__(parent)
        self.tag = tag
        self.count = count
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self._radius = 50
        self._color = QColor(cfg.themeColor.value)

    def boundingRect(self):
        return QRectF(
            -self._radius, -self._radius, 2 * self._radius, 2 * self._radius
        )

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self._color))
        painter.setPen(QPen(self._color.darker(), 2))
        painter.drawEllipse(self.boundingRect())
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(
            self.boundingRect(),
            Qt.AlignmentFlag.AlignCenter,
            f"{self.tag}\n{self.count}",
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.tag)


class ImageNode(QGraphicsPixmapItem):
    _init_node_size: Tuple[int, int] = (100, 100)
    _hovered_node_size: Tuple[int, int] = (150, 150)

    def __init__(self, id: str, image_path: str, pixmap: QPixmap, parent=None):
        self.original_pixmap = pixmap.scaled(
            *self._init_node_size,
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.hovered_pixmap = pixmap.scaled(
            *self._hovered_node_size, Qt.AspectRatioMode.KeepAspectRatio
        )
        super().__init__(self.original_pixmap, parent)

        self.id = id
        self.image_path = image_path
        self.edges = []

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setAcceptHoverEvents(True)

        # For tracking position changes, QGraphicsItem doesn't have a signal
        self.position_changed_callback: Callable[[str, QPointF], None] = None

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self.position_changed_callback:
                self.position_changed_callback(self.id, value)
        return super().itemChange(change, value)

    def add_edge(self, edge):
        self.edges.append(edge)

    def hoverEnterEvent(self, event):
        self.setPixmap(self.hovered_pixmap)
        self.setOffset(-10, -10)

        scene = self.scene()
        if scene:
            for item in scene.items():
                if isinstance(item, Edge):
                    if item in self.edges:
                        item.setOpacity(1.0)
                        item.set_highlighted(True)
                    else:
                        item.setOpacity(0.0)
                        item.set_highlighted(False)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPixmap(self.original_pixmap)
        self.setOffset(0, 0)

        scene = self.scene()
        if scene:
            for item in scene.items():
                if isinstance(item, Edge):
                    item.setOpacity(1.0)
                    item.set_highlighted(False)
                elif isinstance(item, ImageNode):
                    item.setOpacity(1.0)
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        # TODO: open in finder when clicked
        os.system(f'open -R "{self.image_path}"')
        super().mouseDoubleClickEvent(event)


class Edge(QGraphicsItem):
    def __init__(
        self,
        source_node: ImageNode,
        target_node: ImageNode,
        similarity=None,
        parent=None,
    ):
        super().__init__(parent)
        self.source_node = source_node
        self.target_node = target_node
        self.similarity = similarity or 0
        self.highlighted = False
        self.setZValue(-1)

        # Register with nodes
        self.source_node.add_edge(self)
        self.target_node.add_edge(self)

        self.adjust()

    def adjust(self):
        if not self.source_node or not self.target_node:
            return

        self.prepareGeometryChange()
        source_pos = self.source_node.scenePos()
        target_pos = self.target_node.scenePos()

        # Get centers
        source_rect = self.source_node.boundingRect()
        target_rect = self.target_node.boundingRect()

        source_center = QPointF(
            source_pos.x() + source_rect.width() / 2,
            source_pos.y() + source_rect.height() / 2,
        )
        target_center = QPointF(
            target_pos.x() + target_rect.width() / 2,
            target_pos.y() + target_rect.height() / 2,
        )

        self.line = QLineF(source_center, target_center)

    def boundingRect(self):
        extra = 20
        return (
            QRectF(self.line.p1(), self.line.p2())
            .normalized()
            .adjusted(-extra, -extra, extra, extra)
        )

    def set_highlighted(self, highlighted: bool):
        self.highlighted = highlighted
        self.update()

    def paint(self, painter, option, widget=None):
        if not self.source_node or not self.target_node:
            return

        self.adjust()
        if self.line.length() == 0:
            return

        # Set colors based on highlight state
        if self.highlighted:
            line_color = QColor(cfg.themeColor.value)
            text_color = QColor(cfg.themeColor.value)
        else:
            color = QColor("#5c5c5c")
            line_color = color
            text_color = color

        # Draw line
        painter.setPen(QPen(line_color, 1))
        painter.drawLine(self.line)

        # Draw arrow
        angle = math.atan2(-self.line.dy(), self.line.dx())
        arrow_size = 10
        arrow_p1 = self.line.p2() + QPointF(
            math.sin(angle + math.pi / 3) * arrow_size,
            math.cos(angle + math.pi / 3) * arrow_size,
        )
        arrow_p2 = self.line.p2() + QPointF(
            math.sin(angle + math.pi - math.pi / 3) * arrow_size,
            math.cos(angle + math.pi - math.pi / 3) * arrow_size,
        )

        painter.setBrush(line_color)
        painter.drawPolygon(QPolygonF([self.line.p2(), arrow_p1, arrow_p2]))

        # Draw similarity value
        text = f"{self.similarity:.2f}"
        painter.setPen(QPen(text_color))

        # Calculate text position at center of line
        center = QPointF(
            (self.line.p1().x() + self.line.p2().x()) / 2,
            (self.line.p1().y() + self.line.p2().y()) / 2,
        )

        # Get text metrics for positioning
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()

        # Create text rectangle
        text_rect = QRectF(
            center.x() - text_width / 2,
            center.y() - text_height / 2,
            text_width,
            text_height,
        )

        # Draw text
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)


class GraphView(QGraphicsView):
    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._graph = graph
        self._setup_viewport()

    def set_nx_layout(self, name):
        # Layouts are handled by the parent class
        pass

    def clear_graph(self):
        self._scene.clear()
        self._scene.setSceneRect(-2000, -2000, 4000, 4000)
        self._graph = nx.Graph()

    def _setup_viewport(self):
        """Initialize viewport settings for panning and zooming."""
        # Set large scene rect for panning space
        self._scene.setSceneRect(-2000, -2000, 4000, 4000)

        # Enable drag mode and scrollbars
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Better rendering
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )

    def centerView(self):
        """Center the view on the scene content."""
        # Get the bounding rect of all items
        items = self._scene.items()
        if not items:
            return

        # Get the bounding rectangle and its center
        scene_rect = self._scene.itemsBoundingRect()
        center = scene_rect.center()

        # Center the view on this point
        self.centerOn(center)
