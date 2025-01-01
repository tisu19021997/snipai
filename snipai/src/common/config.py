from enum import Enum
from typing import List

from PyQt6.QtCore import QLocale
from qfluentwidgets import (
    BoolValidator,
    ConfigItem,
    ConfigSerializer,
    FolderValidator,
    OptionsConfigItem,
    OptionsValidator,
    QConfig,
    Theme,
    qconfig,
)

from .resources import paths


class Language(Enum):
    """Language enumeration"""

    CHINESE_SIMPLIFIED = QLocale(
        QLocale.Language.Chinese, QLocale.Country.China
    )
    CHINESE_TRADITIONAL = QLocale(
        QLocale.Language.Chinese, QLocale.Country.HongKong
    )
    ENGLISH = QLocale(QLocale.Language.English)
    AUTO = QLocale()


class LanguageSerializer(ConfigSerializer):
    """Language serializer"""

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        return Language(QLocale(value)) if value != "Auto" else Language.AUTO


class HotkeySerializer(ConfigSerializer):
    """Hotkey serializer"""

    def serialize(self, hotkey: str):
        # Split "alt+space" to {"alt", "space"}
        return hotkey.split("+")

    def deserialize(self, value: List[str]):
        return "+".join(value)


class Config(QConfig):
    """Config of application"""

    # files
    image_folder = ConfigItem(
        "Files", "Image directory", paths.IMG, FolderValidator()
    )
    dpi_scale = OptionsConfigItem(
        "MainWindow",
        "DpiScale",
        "Auto",
        OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]),
        restart=True,
    )
    # hotkey
    snip_hotkey = OptionsConfigItem(
        "Hotkeys", "Snip Hotkey", "alt+space", serializer=HotkeySerializer()
    )
    # tags
    tags = ConfigItem("Tags", "Tags", [], restart=False)
    enable_ai_tagging = ConfigItem(
        "Tags", "AutoTagging", False, BoolValidator()
    )


cfg = Config()
cfg.themeMode.value = Theme.AUTO
qconfig.load(paths.CONFIG / "config.json", cfg)
