from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QSize

class InfoButton(QPushButton):
    def __init__(self, parent=None, size=20, bg_color="#3498DB", text_color="#FFFFFF"):
        super().__init__("i", parent)
        self.size = size
        self.bg_color = bg_color
        self.text_color = text_color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        self.setFixedSize(self.size, self.size)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.bg_color};
                color: {self.text_color};
                border: none;
                border-radius: {self.size // 2}px;
                font-weight: bold;
                font-size: {max(12, self.size // 3)}px;
            }}
            QPushButton:hover {{
                background-color: #2980B9;
            }}
            QPushButton:pressed {{
                background-color: #21618C;
            }}
        """)
    
    def sizeHint(self):
        return QSize(self.size, self.size)