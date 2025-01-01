from typing import List, Optional, Union

from loguru import logger
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QWidget,
)
from qfluentwidgets import CustomColorSettingCard, Dialog, ExpandLayout
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    InfoBar,
    OptionsSettingCard,
    PushButton,
    PushSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    SwitchSettingCard,
    ToolButton,
    qconfig,
    setTheme,
    setThemeColor,
)
from qfluentwidgets.components.settings.expand_setting_card import (
    ExpandSettingCard,
)

from snipai.src.common.config import cfg
from snipai.src.common.style_sheet import StyleSheet
from snipai.src.services import StorageService


class TextInputSettingCard(SettingCard):
    """Setting card with text input"""

    textChanged = pyqtSignal(str, str)  # (value, action_key)

    def __init__(
        self,
        key: str,
        icon: Union[str, QIcon, FIF],
        title: str,
        content: Optional[str] = None,
        parent=None,
        default_value: Optional[str] = None,
        placeholder: Optional[str] = None,
    ):
        super().__init__(icon, title, content, parent)

        # Create text input
        self.text_input = QLineEdit(self)
        if placeholder:
            self.text_input.setPlaceholderText(placeholder)
        self.text_input.setText(default_value)
        self.text_input.setFixedHeight(32 if content else 24)

        # Add text input to layout
        self.hBoxLayout.addWidget(
            self.text_input, 0, Qt.AlignmentFlag.AlignRight
        )
        self.hBoxLayout.addSpacing(16)

        # Connect text changed signal
        self.text_input.textChanged.connect(self._on_text_changed)
        self._value = default_value or ""
        # Key.
        self.key = key

    def _on_text_changed(self, text: str):
        self._value = text
        self.textChanged.emit(text, self.key)

    def setValue(self, value: str):
        """Set the value of the text input"""
        self._value = value
        self.text_input.setText(value)

    def value(self) -> str:
        """Get the current value"""
        return self._value


class TagChip(QWidget):
    """Tag chip item with remove button"""

    removed = pyqtSignal(QWidget)

    def __init__(self, tag_name: str, parent=None):
        super().__init__(parent=parent)
        self.tag_name = tag_name
        self.hBoxLayout = QHBoxLayout(self)
        self.tagLabel = QLabel(tag_name, self)
        self.removeButton = ToolButton(FIF.CLOSE, self)

        # Style the chip
        self.removeButton.setFixedSize(24, 24)
        self.removeButton.setIconSize(QSize(10, 10))

        self.setFixedHeight(32)  # More compact than folder item
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Layout setup
        self.hBoxLayout.setContentsMargins(12, 0, 6, 0)
        self.hBoxLayout.addWidget(self.tagLabel)
        self.hBoxLayout.addWidget(self.removeButton)
        self.hBoxLayout.setSpacing(6)
        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Connect remove signal
        self.removeButton.clicked.connect(lambda: self.removed.emit(self))

        # Style sheet for chip-like appearance
        self.setStyleSheet(
            """
            TagChip {
                background-color: #f0f0f0;
                border-radius: 16px;
            }
        """
        )


class TagListSettingCard(ExpandSettingCard):
    """Tag list setting card for managing tags"""

    tagsChanged = pyqtSignal(list)

    def __init__(self, configItem, title, content=None, parent=None):
        super().__init__(FIF.TAG, title, content, parent)
        self.configItem = configItem
        self.addTagButton = PushButton(self.tr("Add tag"), self, FIF.ADD)
        self.tags = (
            qconfig.get(configItem).copy() if qconfig.get(configItem) else []
        )

        self.__initWidget()

    def __initWidget(self):
        self.addWidget(self.addTagButton)

        # Initialize layout with flow-like behavior for tags
        self.flowLayout = QHBoxLayout()
        self.flowLayout.setSpacing(8)
        self.flowLayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.flowLayout.setContentsMargins(48, 0, 48, 0)
        self.viewLayout.addLayout(self.flowLayout)

        # Add existing tags
        for tag in self.tags:
            self.__addTagChip(tag)

        self.addTagButton.clicked.connect(self.__showAddTagDialog)

    def __showAddTagDialog(self):
        """Show dialog to add new tag"""
        dialog = Dialog(
            title=self.tr("Add new tag"),
            content="",  # We'll add a line edit in the dialog
            parent=self.window(),
        )
        dialog.titleLabel.hide()

        # Add line edit to dialog
        lineEdit = QLineEdit(dialog)
        lineEdit.setPlaceholderText(self.tr("Enter tag name"))
        dialog.contentLabel.hide()  # Hide the content label
        dialog.textLayout.insertWidget(
            1, lineEdit
        )  # Add line edit after title

        def add_tag():
            tag_name = lineEdit.text().strip()
            if tag_name and tag_name not in self.tags:
                self.__addTagChip(tag_name)
                self.tags.append(tag_name)
                self.tagsChanged.emit(self.tags)
                self.tags.sort()
                qconfig.set(self.configItem, self.tags)
                dialog.accept()

        dialog.yesSignal.connect(add_tag)
        dialog.exec()

    def __addTagChip(self, tag_name: str):
        """Add a new tag chip"""
        chip = TagChip(tag_name, self.view)
        chip.removed.connect(self.__showRemoveConfirmDialog)
        self.flowLayout.addWidget(chip)
        chip.show()
        self._adjustViewSize()

    def __showRemoveConfirmDialog(self, chip: TagChip):
        """Show confirm dialog for tag removal"""
        title = self.tr("Remove tag?")
        content = (
            self.tr("Are you sure you want to remove the tag ")
            + f'"{chip.tag_name}"?'
        )
        dialog = Dialog(title, content, self.window())
        dialog.yesSignal.connect(lambda: self.__removeTag(chip))
        dialog.exec()

    def __removeTag(self, chip: TagChip):
        """Remove a tag chip"""
        if chip.tag_name not in self.tags:
            return

        # TODO: also delete from database (Image table, Tag table, ImageTag table)
        self.tags.remove(chip.tag_name)
        self.flowLayout.removeWidget(chip)
        chip.deleteLater()
        self._adjustViewSize()

        self.tagsChanged.emit(self.tags)
        qconfig.set(self.configItem, self.tags)

    def __removeTagByName(self, tag_name: str):
        """Remove a tag by its name from layout and internal list"""
        for i in range(self.flowLayout.count()):
            chip = self.flowLayout.itemAt(i).widget()
            if chip and chip.tag_name == tag_name:
                self.tags.remove(tag_name)
                self.flowLayout.removeWidget(chip)
                chip.deleteLater()
                self._adjustViewSize()
                qconfig.set(self.configItem, self.tags)
                break


class SettingInterface(ScrollArea):
    """Setting interface"""

    def __init__(self, storage_service: StorageService, parent=None):
        super().__init__(parent=parent)
        self.storage_service = storage_service

        self.scroll_widget = QWidget()
        self.expand_layout = ExpandLayout(self.scroll_widget)
        self.scroll_widget.setObjectName("scrollWidget")

        # setting label
        self.setting_label = QLabel(self.tr("Settings"), self)
        self.setting_label.setObjectName("settingLabel")

        self.setObjectName("SettingInterface")
        StyleSheet.SETTING_INTERFACE.apply(self)

        # music folders
        self.files_group = SettingCardGroup(
            self.tr("Files"), self.scroll_widget
        )
        self.image_folder_card = PushSettingCard(
            self.tr("Choose folder"),
            FIF.DOWNLOAD,
            self.tr("Download directory"),
            cfg.get(cfg.image_folder),
            self.files_group,
        )
        # ---

        # personalization
        self.personal_group = SettingCardGroup(
            self.tr("Personalization"), self.scroll_widget
        )
        self.theme_card = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            self.tr("Application theme"),
            self.tr("Change the appearance of your application"),
            texts=[
                self.tr("Light"),
                self.tr("Dark"),
                self.tr("Use system setting"),
            ],
            parent=self.personal_group,
        )
        self.theme_color_card = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            self.tr("Theme color"),
            self.tr("Change the theme color of you application"),
            parent=self.personal_group,
        )
        # ---

        # hotkeys
        self.hotkeys_group = SettingCardGroup(
            self.tr("Hotkeys"), self.scroll_widget
        )
        self.snip_hotkey_card = TextInputSettingCard(
            "snip_start",
            FIF.CAMERA,
            self.tr("Snip"),
            self.tr(
                'Hotkey to start the snipping tool, separate each key by a "+"'
            ),
            parent=self.hotkeys_group,
            default_value="alt+space",
        )

        # tags
        self.tags_group = SettingCardGroup(self.tr("Tags"), self.scroll_widget)
        self.tags_card = TagListSettingCard(
            cfg.tags,  # use the config item from cfg
            self.tr("Tags"),
            self.tr("Add and manage tags for your images"),
            parent=self.tags_group,
        )
        self.enable_ai_tagging_card = SwitchSettingCard(
            FIF.TAG,
            self.tr("AI Tagging"),
            self.tr("AI will automatically tag your images using your tags"),
            configItem=cfg.enable_ai_tagging,
            parent=self.tags_group,
        )

        self.__init_widget()

    @property
    def hotkey_settings(self):
        return [self.snip_hotkey_card]

    def __init_widget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scroll_widget)
        self.setWidgetResizable(True)

        # initialize layout
        self.__init_layout()
        self.__connect_signal_to_slot()

    def __init_layout(self):
        self.setting_label.move(36, 30)

        # add cards to group
        self.files_group.addSettingCard(self.image_folder_card)

        self.personal_group.addSettingCard(self.theme_card)
        self.personal_group.addSettingCard(self.theme_color_card)

        self.hotkeys_group.addSettingCard(self.snip_hotkey_card)

        # add tags card to group
        self.tags_group.addSettingCards(
            [self.tags_card, self.enable_ai_tagging_card]
        )

        # add setting card group to layout
        self.expand_layout.setSpacing(28)
        self.expand_layout.setContentsMargins(36, 10, 36, 0)
        for group in [
            self.files_group,
            self.personal_group,
            self.hotkeys_group,
            self.tags_group,
        ]:
            self.expand_layout.addWidget(group)

        # Initialize tags from config
        self.storage_service.update_tags(self.tags_card.tags)

    def __show_restart_tooltip(self):
        """show restart tooltip"""
        InfoBar.success(
            self.tr("Updated successfully"),
            self.tr("Configuration takes effect after restart"),
            duration=1500,
            parent=self,
        )

    def __on_image_folder_card_clicked(self):
        """download folder card clicked slot"""
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Choose folder"), "./"
        )
        if not folder or cfg.get(cfg.image_folder) == folder:
            return

        cfg.set(cfg.image_folder, folder, save=True)
        self.image_folder_card.setContent(folder)

    def __on_changing_snip_hotkey_card(self, hotkey: str):
        """snip hotkey card changed slot"""
        # Save to config file.
        cfg.set(cfg.snip_hotkey, hotkey, save=True)

    def __connect_signal_to_slot(self):
        """connect signal to slot"""
        cfg.appRestartSig.connect(self.__show_restart_tooltip)

        self.image_folder_card.clicked.connect(
            self.__on_image_folder_card_clicked
        )

        # personalization
        cfg.themeChanged.connect(setTheme)
        self.theme_color_card.colorChanged.connect(lambda c: setThemeColor(c))

        self.snip_hotkey_card.textChanged.connect(
            self.__on_changing_snip_hotkey_card
        )

        # connect tags changed signal
        self.tags_card.tagsChanged.connect(self.__on_tags_changed)

    def __on_tags_changed(self, tags: List[str]):
        """Handle tags changes"""
        # Tags are already saved to config by the card
        # You can add additional handling here if needed
        try:
            self.storage_service.update_tags(tags=tags)
            if not tags:
                self.enable_ai_tagging_card.setDisabled(True)
            else:
                self.enable_ai_tagging_card.setDisabled(False)

            logger.info(f"Tags saved successfully: {tags}")
        except Exception as e:
            logger.error(f"Tags saved failed: {str(e)}")
        except Exception as e:
            logger.error(f"Tags saved failed: {str(e)}")
