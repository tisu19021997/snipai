import os
from functools import lru_cache
from typing import List, Optional, Tuple

from PyQt6.QtCore import QEasingCurve, Qt, pyqtSlot
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    CheckBox,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    PipsPager,
    PipsScrollButtonDisplayMode,
    RoundMenu,
    ScrollArea,
    TitleLabel,
)
from typing_extensions import TypedDict

from snipai.src.common.style_sheet import StyleSheet
from snipai.src.common.types import TimeFilter
from snipai.src.model.image import Image, Tag
from snipai.src.services.storage import StorageService
from snipai.src.ui.components import ImageCard, SnipSearchBar, WaterfallLayout
from snipai.src.ui.components.multi_combo_box import MultiSelectionComboBox

NO_TAG_FILTER = "__all__"


class InterfaceState(TypedDict):
    query: str = ""
    time_filter: TimeFilter = TimeFilter.ALL_TIME
    tags: Tuple[str] = tuple([NO_TAG_FILTER])
    page: int = 0
    per_page: int = 42


class TagSelectionDialog(MessageBox):
    def __init__(
        self,
        parent=None,
        selected_tags: Optional[List[Tag]] = None,
        available_tags: Optional[List[Tag]] = None,
    ):
        super().__init__(title=self.tr("Add Tags"), content="", parent=parent)
        self.available_tags = available_tags or []
        self.selected_tags = selected_tags or []

        # Add checkboxes for each tag
        for tag in self.available_tags:
            checkbox = CheckBox(tag.name, self)
            if tag in self.selected_tags:
                checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda checked, t=tag: self._on_tag_toggled(t, checked)
            )
            self.textLayout.addWidget(checkbox)

        # Set up buttons
        self.yesButton.setText("Save")
        # self.yesButton.setIcon(FluentIcon.ADD)
        self.cancelButton.setText("Cancel")

    def _on_tag_toggled(self, tag: Tag, checked: bool):
        if checked and tag not in self.selected_tags:
            self.selected_tags.append(tag)
        elif not checked and tag in self.selected_tags:
            self.selected_tags.remove(tag)

    @property
    def tags(self):
        return self.selected_tags


class BookmarksInterface(ScrollArea):
    IMAGES_PER_PAGE = 42
    IMAGE_WIDTH = 200
    ALL_TAGS_DISPLAY = "All tags"

    def __init__(self, storage_service: StorageService, parent=None):
        super().__init__(parent)
        self.title_label = TitleLabel(self.tr("Your Snips"), self)

        self.storage_service = storage_service
        self.storage_service.image_saved.connect(self._update_current_page)
        self.storage_service.image_deleted.connect(self._on_image_deleted)
        self.storage_service.image_desc_updated.connect(self._on_image_updated)
        self.storage_service.tag_added.connect(self._on_image_updated)

        self._tags = self.storage_service.get_all_tags()

        # Create widgets
        self.view = QWidget(self)
        self.vbox_layout = QVBoxLayout(self.view)
        self.flow_layout = WaterfallLayout(
            None,
            default_col_width=self.IMAGE_WIDTH,
            needAni=True,
            isTight=False,
        )
        self.pager = PipsPager(Qt.Orientation.Horizontal)
        self.context_menu = RoundMenu(self)
        self.context_menu.hide()

        self._reset_state()
        self._init_widget()
        self._init_layout()
        self._init_pagination()
        self._connect_signals()

    def _init_widget(self):
        self.view.setObjectName("view")
        self.setObjectName("BookmarkInterface")
        StyleSheet.HOME_INTERFACE.apply(self)

        # Setup scroll area
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        # Setup flow layout
        self.flow_layout.setAnimation(500, QEasingCurve.Type.OutQuart)
        self.flow_layout.setContentsMargins(12, 12, 12, 12)
        # self.flow_layout.setSpacing(32)
        self.flow_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def _init_layout(self):
        self.search_bar = SnipSearchBar()
        self.search_bar.setPlaceholderText(self.tr("Search your snips"))

        self.time_filter = ComboBox()
        self.time_filter.addItems([op.value for op in TimeFilter])
        self.time_filter.setPlaceholderText(TimeFilter.ALL_TIME.value)

        self.tag_filter_multi = MultiSelectionComboBox()
        self.tag_filter_multi.addItems(
            [tag.name for tag in self.storage_service.get_all_tags()]
        )
        self.tag_filter_multi.setPlaceholderText(
            self.tr(self.ALL_TAGS_DISPLAY)
        )

        self.vbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.vbox_layout.setContentsMargins(36, 20, 36, 36)
        self.vbox_layout.setSpacing(20)
        self.vbox_layout.addWidget(self.title_label)
        self.vbox_layout.addSpacing(4)

        # Add a search bar.
        self.vbox_layout.addWidget(self.search_bar)
        # Add layout for filters
        hbox_layout = QHBoxLayout()
        hbox_layout.setContentsMargins(0, 0, 0, 0)
        hbox_layout.setSpacing(20)
        hbox_layout.addWidget(self.time_filter)
        hbox_layout.addWidget(self.tag_filter_multi)
        self.filters_layout = hbox_layout

        self.vbox_layout.addLayout(self.filters_layout)
        # Add the images grid.
        self.vbox_layout.addLayout(self.flow_layout)
        self.vbox_layout.addWidget(
            self.pager, alignment=Qt.AlignmentFlag.AlignBottom
        )
        # Load first page
        self._update_view()

    def _connect_signals(self):
        self.pager.currentIndexChanged.connect(self._go_to_page)
        self.search_bar.searchSignal.connect(self._search_images)
        self.search_bar.clearSignal.connect(self._on_search_bar_clear)
        self.search_bar.textEdited.connect(
            lambda text: (
                self._on_search_bar_clear()
                if text == "" and self.state.get("query")
                else None
            )
        )
        # Add filter callbacks
        self.time_filter.currentTextChanged.connect(
            self._on_time_filter_changed
        )
        self.tag_filter_multi.selectionChanged.connect(
            self._on_tag_filter_changed
        )

    def _init_pagination(self):
        """Initialize pagination by loading first page and setting up pager"""
        # Calculate total pages
        # Setup pager
        self.pager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.pager.setPreviousButtonDisplayMode(
            PipsScrollButtonDisplayMode.ALWAYS
        )

        # Update pager
        self.pager.setPageNumber(max(1, self.total_pages))
        self.pager.setVisibleNumber(max(1, self.total_pages))

    @property
    def total_pages(self):
        return (
            self.total_images + self.IMAGES_PER_PAGE - 1
        ) // self.IMAGES_PER_PAGE

    @lru_cache(maxsize=10)
    def _fetch_images(
        self,
        query: Optional[str] = None,
        time_filter: Optional[str] = None,
        tags: Optional[
            tuple
        ] = None,  # Using tuple since lists aren't hashable
        page: int = 0,
        per_page: int = 42,
    ) -> Tuple[List[Image], int]:
        """
        Fetch images from storage with caching.

        The @lru_cache decorator automatically caches results based on the
        input parameters. When the same parameters are used again,
        it returns cached results instead of querying the database.
        """
        return self.storage_service.hybrid_search_images(
            query=query,
            time_filter=time_filter,
            tags=(
                list(tags)
                if tags and self.ALL_TAGS_DISPLAY not in tags
                else None
            ),  # Convert back to list for storage service
            page=page,
            per_page=per_page,
        )

    def _search_images(self, query: str):
        """Search images based on query"""
        self.state.update({"query": query or None, "page": 0})
        self._update_view()

    @pyqtSlot(int)
    def _go_to_page(self, page: int = 0):
        """Handle page change event"""
        self.state.update({"page": page})
        self._update_view()

    def _on_search_bar_clear(self):
        self.state.update({"query": None, "page": 0})
        self._update_view()

    def _update_view(self):
        """Update view with filtered images"""
        self.images, self.total_images = self._fetch_images(**self.state)

        # Also fetch all the tags associated with the images
        all_image_tags = self.storage_service.get_image_tags_batch(
            [img.id for img in self.images]
        )
        for img in self.images:
            img.tags = all_image_tags.get(img.id, [])

        self._render_images()
        self._render_pager()

    def _on_time_filter_changed(self, time_filter: str):
        self.state.update(
            {"time_filter": TimeFilter(value=time_filter), "page": 0}
        )
        self._update_view()

    def _on_tag_filter_changed(self, selected_tags: List[str]):
        cur_tags = list(self.state.get("tags"))
        if selected_tags == cur_tags:
            return

        self.state.update({"tags": tuple(selected_tags), "page": 0})
        self._update_view()

    def _update_current_page(self, image_id: str):
        """Update the flow UI everytime new image is added."""
        # Clear the cache since data has changed
        self._fetch_images.cache_clear()

        image = self.storage_service.load_image(image_id)
        image_ui = self._image_to_ui(image)
        self.flow_layout.insertWidget(0, image_ui)

    def _on_image_deleted(self, image_id: str):
        """Handle image deletion signal from storage service."""
        InfoBar.success(
            title="Image Deleted",
            content="Deleted the image",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )
        # Clear the cache since data has changed
        self._fetch_images.cache_clear()

        # Find and remove the widget for the deleted image
        for i in range(self.flow_layout.count()):
            widget = self.flow_layout.itemAt(i).widget()
            if widget and widget.property("image_id") == image_id:
                self.flow_layout.removeWidget(widget)
                widget.deleteLater()
                break

        # Update total images count and pagination
        self.total_images -= 1
        if self.total_images < 0:
            self.total_images = 0

        # If current page is now empty and not the first page,
        # go to previous page
        if not self.flow_layout.count() and self.state["page"] > 0:
            self.state["page"] -= 1
        # If we're on the first page or there are still images,
        # just update the pager
        else:
            # Force layout update to fill the gap
            self.flow_layout.setGeometry(self.flow_layout.geometry())
            self._render_pager()
        self._update_view()

    def _on_image_updated(self, **kwargs):
        """Clear cache and update the current image view"""
        # TODO: Single image updated but re-render all page?
        self._fetch_images.cache_clear()
        self._update_view()

    def _render_images(self):
        """Load and display images for the current page"""
        # Block signals during widget removal
        self.flow_layout.blockSignals(True)
        # Clear current items
        self.flow_layout.takeAllWidgets()
        self.flow_layout.blockSignals(False)

        # Add images to layout
        for image in self.images:
            # Create image widget
            image_label = self._image_to_ui(image)
            # Add to layout
            self.flow_layout.addWidget(image_label)

    def _render_pager(self):
        # Update pager
        self.pager.setVisibleNumber(self.total_pages)
        old_state = self.pager.blockSignals(True)
        self.pager.setCurrentIndex(self.state["page"])
        self.pager.blockSignals(old_state)

    def _copy_image_to_clipboard(self, image: Image):
        """Copy image to clipboard"""
        clipboard = QApplication.clipboard()
        pixmap = QPixmap(str(self.storage_service.images_dir / image.filepath))
        clipboard.setPixmap(pixmap)

    def _show_image_tags(self, image: Image):
        """Show dialog to add tags to an image"""
        # Get available tags from storage service
        available_tags = (
            self.storage_service.get_all_tags()
        )  # You'll need to implement this

        dialog = TagSelectionDialog(
            selected_tags=image.tags,
            parent=self.window(),
            available_tags=available_tags,
        )
        # New tags added.
        if dialog.exec():
            selected_tags = dialog.tags
            # Add tags to image
            updated_image = self.storage_service.update_image_tags(
                image.id, selected_tags
            )

            if updated_image:
                # Show success message
                InfoBar.success(
                    title="Tags Added",
                    content=f"Successfully updated tags to {image.filename}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self,
                )

    def _image_to_ui(self, image: Image):
        filepath = self.storage_service.images_dir / image.filepath
        image_card = ImageCard(
            str(filepath),
            image.filename,
            description=image.description,
            default_width=self.IMAGE_WIDTH,
            parent=self.window(),
            storage_service=self.storage_service,
        )
        image_card.setProperty("image_id", image.id)

        def show_context_menu(pos):
            self.context_menu.clear()
            # Get all items and explicitly remove them
            for i in reversed(range(self.context_menu.view.count())):
                self.context_menu.view.takeItem(i)

            filepath = self.storage_service.images_dir / image.filepath

            # Add menu actions
            self.context_menu.addAction(
                Action(
                    FluentIcon.TAG,
                    self.tr("Add Tags"),
                    triggered=lambda: self._show_image_tags(image),
                )
            )
            self.context_menu.addAction(
                Action(
                    FluentIcon.COPY,
                    self.tr("Copy"),
                    triggered=lambda: self._copy_image_to_clipboard(image),
                )
            )
            self.context_menu.addAction(
                Action(
                    FluentIcon.FOLDER,
                    self.tr("Show in Finder"),
                    triggered=lambda: os.system(f'open -R "{filepath}"'),
                )
            )
            self.context_menu.addSeparator()
            self.context_menu.addAction(
                Action(
                    FluentIcon.DELETE,
                    self.tr("Delete"),
                    triggered=lambda: self.storage_service._delete_image(
                        image
                    ),
                )
            )
            # Show menu at cursor position
            self.context_menu.exec(image_card.mapToGlobal(pos))

        image_card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        image_card.customContextMenuRequested.connect(show_context_menu)
        return image_card

    def _reset_state(self):
        # Reset state
        self.state = InterfaceState(
            query=None,
            time_filter=TimeFilter.ALL_TIME,
            tags=tuple([self.ALL_TAGS_DISPLAY]),
            page=0,
            per_page=self.IMAGES_PER_PAGE,
        )

    def refresh(self):
        """Refresh the image gallery"""
        self._fetch_images.cache_clear()
        self._reset_state()
        self.pager.setCurrentIndex(0)
        self._init_pagination()
