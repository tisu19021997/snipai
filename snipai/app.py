import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from snipai.src.common.config import cfg
from snipai.src.ui.view.window import Window

# enable dpi scale
if cfg.get(cfg.dpi_scale) != "Auto":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpi_scale))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)
    w = Window()
    w.show()
    app.exec()
