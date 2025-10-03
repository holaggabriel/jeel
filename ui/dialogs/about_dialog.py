from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acerca de")
        self.setFixedSize(250, 180)  # Ajusté un poco el tamaño para el enlace
        
        layout = QVBoxLayout()
        
        title = QLabel("🎬 Jeel")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        version_label = QLabel("Versión: 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        author_label = QLabel("Autor: Gabriel Beltran")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_label)
        
        # Aquí agregamos el enlace a GitHub
        github_label = QLabel('<a href="https://github.com/holaggabriel/jeel">GitHub</a>')
        github_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        github_label.setOpenExternalLinks(True)  # Muy importante para que abra el enlace
        layout.addWidget(github_label)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
