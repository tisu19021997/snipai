import os
import sys

from PyQt6.QtWidgets import QApplication

file_path = os.path.abspath(__file__)
home_dir = os.path.dirname(file_path)
os.environ["APP_HOME_DIR"] = home_dir

from src.ui.window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # Run the event loop
    sys.exit(app.exec())
