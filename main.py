import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MusicDownloader

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MusicDownloader()
    window.show()
    sys.exit(app.exec()) 