from typing import Optional

from loguru import logger
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QGuiApplication, QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    ElevatedCardWidget,
    FluentStyleSheet,
    ImageLabel,
    PlainTextEdit,
)
from sqlmodel import select

from snipai.src.common.db import Database
from snipai.src.model.image import Image
from snipai.src.services import StorageService


class ImageCard(ElevatedCardWidget):
    """A card widget that adapts to image dimensions for waterfall layout"""

    def __init__(
        self,
        image_path: str,
        caption: str,
        description: str = "",
        default_width: int = 240,
        parent=None,
        storage_service: Optional[StorageService] = None,
    ):
        super().__init__(parent)
        self.image_label = ImageLabel(self)
        self.image_path = image_path
        self.caption = caption
        self._description_changed = False

        # Load the original pixmap to get dimensions
        self.original_pixmap = QPixmap(str(image_path))

        # Set up layout
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setSpacing(8)
        self.vBoxLayout.setContentsMargins(8, 8, 8, 8)
        self.vBoxLayout.addWidget(self.image_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.storage_service = storage_service

        # Set tooltip
        if description:
            self.setToolTip(f"{caption}\n\n{description}")
        else:
            self.setToolTip(caption)

        self.image_label.setContentsMargins(0, 0, 0, 0)
        self.image_label.setObjectName("windowTitleLabel")
        # Initial resize
        self.updateImageSize(default_width)  # Default width

        # Enable double-click event
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.mouseDoubleClickEvent = self._on_double_click

    def updateImageSize(self, width):
        """Update image size maintaining aspect ratio"""
        content_width = (
            width
            - self.vBoxLayout.contentsMargins().left()
            - self.vBoxLayout.contentsMargins().right()
        )

        # Calculate height based on original aspect ratio
        aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()
        content_height = int(content_width / aspect_ratio)

        # Set image size
        self.image_label.setFixedSize(content_width, content_height)

        # Scale pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            content_width,
            content_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

        # Set card size (add margins and spacing)
        total_height = (
            content_height
            + self.vBoxLayout.contentsMargins().top()
            + self.vBoxLayout.contentsMargins().bottom()
        )
        self._preferredWidth = width
        self._preferredHeight = total_height
        self.resize(width, total_height)

    def sizeHint(self):
        """Return the preferred size of the widget"""
        return QSize(self._preferredWidth, self._preferredHeight)

    def minimumSizeHint(self):
        """Return the minimum size of the widget"""
        return QSize(100, 100)  # Minimum reasonable size for the card

    def _set_style(self):
        self.setStyleSheet(
            """
            ImageCard {
                border-radius: 8px;
            }
        """
        )
        self.image_label.setStyleSheet(
            """
            ImageLabel {
                border-radius: 8px;
            }
        """
        )

    def _on_double_click(self, event):
        """Handle double-click event to show the image in a larger window"""
        self.show_larger_image()

    def show_larger_image(self):
        """Show the image in a larger window with an editable description overlay"""
        # Create a new dialog
        dialog = QDialog(self)
        FluentStyleSheet.DIALOG.apply(self)
        dialog.setWindowTitle(self.caption)
        dialog.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
        )

        # Create a layout for the dialog
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create a QLabel to display the larger image
        image_label = QLabel(dialog)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Load the original image and scale it to fit the screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            max_width = screen_geometry.width() - 100  # Leave some margin
            max_height = screen_geometry.height() - 100

            # Calculate scaled size maintaining aspect ratio
            aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()
            if self.original_pixmap.width() > max_width:
                scaled_width = max_width
                scaled_height = int(scaled_width / aspect_ratio)
            else:
                scaled_width = self.original_pixmap.width()
                scaled_height = self.original_pixmap.height()

            if scaled_height > max_height:
                scaled_height = max_height
                scaled_width = int(scaled_height * aspect_ratio)

            scaled_pixmap = self.original_pixmap.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image_label.setPixmap(scaled_pixmap)

        # Add the image label to the dialog layout
        layout.addWidget(image_label)

        # Create a description overlay
        if self.toolTip():  # Use the tooltip as the description
            overlay = QWidget(dialog)
            overlay.setFixedHeight(80)  # Height of the overlay

            # Create a layout for the overlay
            overlay_layout = QVBoxLayout(overlay)
            overlay_layout.setContentsMargins(10, 5, 10, 5)

            description_edit = PlainTextEdit(overlay)
            description_edit.setPlaceholderText("Write something about the image...")

            # Set the initial description text (remove the name)
            description_text = self.toolTip().split("\n\n")[
                -1
            ]  # Get only the description
            description_edit.setPlainText(description_text)

            # Set the width of the description edit to match the image width
            description_edit.setFixedWidth(scaled_pixmap.width())
            description_edit.textChanged.connect(self._on_description_changed)

            # Add the description edit to the overlay layout
            overlay_layout.addWidget(
                description_edit, alignment=Qt.AlignmentFlag.AlignCenter
            )

            # Add the overlay to the dialog layout
            layout.addWidget(overlay)

        # Set the dialog size to fit the scaled image
        dialog.resize(scaled_pixmap.width(), scaled_pixmap.height())

        # Save the description when the dialog is closed
        dialog.finished.connect(
            lambda: self._save_description(dialog, description_edit.toPlainText())
        )

        # Show the dialog
        dialog.exec()

    def _on_description_changed(self):
        """Update the overlay with the new description"""
        self._description_changed = True

    def _save_description(self, _: QDialog, description: str):
        """Save the updated description to the database"""
        if not self._description_changed:
            return

        # Get the image ID from the card (assuming it's stored as a property)
        image_id = self.property("image_id")
        if not image_id:
            logger.error("Image ID not found in the card properties")
            return

        # Update the description in the database
        with Database.session() as session:
            stmt = select(Image).where(Image.id == image_id)
            image = session.exec(stmt).one()
            image.description = description.strip()
            session.add(image)
            session.commit()

        # Emit a signal to notify that the description has been updated
        self.storage_service.image_desc_updated.emit(image_id, description)
        self.storage_service.any2emb.encode(text=description, task_id=image_id)
        self.storage_service.metadata_service.set_description(
            self.image_path, description
        )

        self._description_changed = False
