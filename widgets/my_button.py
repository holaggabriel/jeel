# ui/custom_button.py
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt

class MyButton(QPushButton):
    def __init__(self, text="Botón", bg_color="#3498DB", text_color="#FFFFFF", parent=None):
        super().__init__(text, parent)
        self.bg_color = bg_color
        self.text_color = text_color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.bg_color};
                color: {self.text_color};
                border: none;
                padding: 8px 15px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """)
