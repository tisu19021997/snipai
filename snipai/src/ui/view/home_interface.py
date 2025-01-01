from typing import Dict, List

import networkx as nx
import numpy as np
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import PushButton, ScrollArea, TitleLabel

from snipai.src.common.style_sheet import StyleSheet
from snipai.src.model.image import Image
from snipai.src.services.storage import StorageService
from snipai.src.ui.components.graph_settings import GraphSettingsPanel
from snipai.src.ui.components.network_graph import (
    ClusterNode,
    Edge,
    GraphView,
    ImageNode,
)


class HomeInterface(ScrollArea):
    def __init__(self, storage_service: StorageService, parent=None):
        super().__init__(parent)
        self.setObjectName("HomeInterface")

        self._current_k = 200
        self._current_iterations = 50
        self._current_scale = 200
        self._normalized_pos = None
        self._image_nodes = {}

        self.storage_service = storage_service
        self.title_label = TitleLabel(self.tr("Explore (experimental)"), self)
        self.mode = "cluster"

        # Initialize container and layout
        self.container = QWidget()
        self.container.setObjectName("view")
        self.container.setContentsMargins(12, 12, 12, 12)
        self.container_layout = QVBoxLayout(self.container)

        # Initialize graph view
        self.view = GraphView(nx.Graph())
        self.view.setObjectName("view")

        self._init_ui()
        StyleSheet.HOME_INTERFACE.apply(self)

        self._init_signals()

    def _init_signals(self):
        """Connect all settings panel signals to their handlers."""
        # Connect scale slider
        self.settings_panel.scale_slider.valueChanged.connect(
            self._handle_scale_change
        )

        # Connect force parameter sliders
        self.settings_panel.k_slider.valueChanged.connect(
            self._handle_force_change
        )
        self.settings_panel.iterations_slider.valueChanged.connect(
            self._handle_force_change
        )

    def _init_ui(self):
        # Initialize scroll area
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setWidget(self.container)
        self.setWidgetResizable(True)

        # Initialize controls
        # self.choice_combo = ComboBox()
        # self.choice_combo.addItems(self.view.get_nx_layouts())
        # self.choice_combo.currentTextChanged.connect(self.view.set_nx_layout)

        self.back_button = PushButton("Back to Clusters")
        self.back_button.clicked.connect(self.display_tag_clusters)
        self.back_button.hide()

        self.settings_panel = GraphSettingsPanel(self)
        self.settings_panel.show()

        self._current_scale = self.settings_panel.scale_slider.value()
        self._current_k = self.settings_panel.k_slider.value()
        self._current_iterations = (
            self.settings_panel.iterations_slider.value()
        )

        # Add widgets to layout
        # self.container_layout.addWidget(self.choice_combo)
        self.container_layout.addWidget(self.title_label)
        self.container_layout.addWidget(self.view)
        self.container_layout.addWidget(self.back_button)

        self.display_tag_clusters()

    def display_tag_clusters(self):
        """Create and display the tag cluster view."""
        self.clear_graph()
        graph = nx.Graph()

        # Create cluster nodes for each tag
        tag_nodes = {}
        for tag, count in self.storage_service.get_all_tags(with_count=True):
            graph.add_node(tag.name)
            node = ClusterNode(tag.name, count)
            self.view.scene().addItem(node)
            tag_nodes[tag.name] = node
            node.clicked.connect(
                lambda t=tag.name: self.display_image_network(t)
            )

        # Position nodes in a circular layout
        layout = nx.circular_layout(graph, scale=1.0)
        # Find center position for the layout
        center_x = 0
        center_y = 0

        # Position nodes around this center with appropriate scaling
        radius = self._current_scale
        for tag_name, node in tag_nodes.items():
            pos = layout[tag_name]
            # Scale the position from [-1,1] range to our desired size
            x = center_x + pos[0] * radius
            y = center_y + pos[1] * radius
            node.setPos(x, y)

        self.mode = "cluster"
        self.back_button.hide()
        self.view.centerView()

    def display_image_network(self, tag_name: str):
        """Display images and their relationships for a given tag."""
        self.clear_graph()
        self.back_button.show()

        # Get images for this tag
        images, _ = self.storage_service.hybrid_search_images(tags=[tag_name])
        if not images:
            return

        image_nodes, similarities = self._build_image_similarity_network(
            images
        )
        if not image_nodes:
            return

        self._layout_image_nodes(image_nodes, similarities)
        self.view._setup_viewport()
        self.view.centerView()

    def _build_image_similarity_network(
        self, images: List[Image], threshold=0.5
    ):
        """Create image nodes and similarity edges."""
        image_nodes = {}
        similarities = {}

        # Create nodes
        for image in images:
            image_path = str(self.storage_service.images_dir / image.filepath)
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                node = ImageNode(image.id, image_path, pixmap)
                node.position_changed_callback = (
                    self._handle_node_position_change
                )
                self.view.scene().addItem(node)
                image_nodes[image.id] = node

        if not image_nodes:
            return None, None

        # Create edges based on similarities
        for img1 in images:
            if img1.id not in image_nodes:
                continue
            similarities[img1.id] = {}
            for img2 in images:
                if (
                    img2.id not in image_nodes
                    or img1.id == img2.id
                    or not img1.description
                    or not img2.description
                ):
                    continue

                sim = self.storage_service.compute_similarity(img1.id, img2.id)
                if sim > threshold:
                    similarities[img1.id][img2.id] = sim
                    edge = Edge(
                        image_nodes[img1.id],
                        image_nodes[img2.id],
                        similarity=sim,
                    )
                    self.view.scene().addItem(edge)

        return image_nodes, similarities

    def _handle_node_position_change(self, node_id: str, new_pos: QPointF):
        """Update normalized positions when a node is moved."""
        if self._normalized_pos and node_id in self._normalized_pos:
            # Convert the new position back to normalized coordinates
            self._normalized_pos[node_id] = np.array(
                [
                    new_pos.x() / self._current_scale,
                    new_pos.y() / self._current_scale,
                ]
            )

    def _layout_image_nodes(
        self,
        image_nodes: Dict[str, ImageNode],
        similarities: Dict[str, Dict[str, float]],
    ):
        """Position nodes using NetworkX's force-directed spring layout."""
        if not image_nodes:
            return

        # Create NetworkX graph from similarities
        G = nx.Graph()
        G.add_nodes_from(image_nodes.keys())

        # Add edges with weights based on similarities
        for node1, sim_dict in similarities.items():
            for node2, sim in sim_dict.items():
                G.add_edge(node1, node2, weight=sim)

        # Compute layout using spring_layout
        if not self._normalized_pos:
            self._normalized_pos = nx.spring_layout(
                G,
                k=self._current_k,
                iterations=self._current_iterations,
                seed=42,
            )
        self._image_nodes = image_nodes
        # Scale the positions to our desired size
        self._update_node_positions()

    def _handle_force_change(self, value: int):
        """Handle changes to the force parameters."""
        # TODO: this is incorrect, 2 sliders are using the same signal
        self._current_k = value
        self._update_node_positions()

    def _handle_scale_change(self, value: int):
        """Handle changes to the scale slider, value is between 25 and 4."""
        if not self._image_nodes:
            return

        self._current_scale = value
        # Update positions
        self._update_node_positions()
        # self._update_node_sizes(value)

    def _update_node_sizes(self, value: int):
        """Update the size of all nodes."""
        for node in self._image_nodes.values():
            scaled_size = (
                int(node._init_node_size[0] * value / self._current_scale),
                int(node._init_node_size[1] * value / self._current_scale),
            )
            node.setPixmap(
                node.original_pixmap.scaled(
                    *scaled_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _update_node_positions(self):
        """Reposition all nodes using the current scale."""
        # We need to store the original normalized positions
        if not self._normalized_pos or not self._image_nodes:
            return

        for node_id, coords in self._normalized_pos.items():
            if node_id in self._image_nodes:
                x, y = coords
                self._image_nodes[node_id].setPos(
                    x * self._current_scale, y * self._current_scale
                )

    def clear_graph(self):
        """Clear the graph and reset all variables"""
        self._image_nodes = {}
        self._normalized_pos = None
        self.view.clear_graph()

    def resizeEvent(self, event):
        """Handle window resizing."""
        super().resizeEvent(event)
        # Reposition settings panel when window is resized
        if hasattr(self, "settings_panel"):
            self.settings_panel.move_to_bottom_right()
