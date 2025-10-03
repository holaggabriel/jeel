import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import ModernVideoConverterApp

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("QMainWindow, QWidget { background-color: #1E1E1E; color: #FFFFFF; }")
    window = ModernVideoConverterApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()