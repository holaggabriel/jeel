import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox

from ui.widgets.my_button import MyButton
from core.converter import ConversionThread
from ui.dialogs.about_dialog import AboutDialog
from ui.widgets.info_button import InfoButton 

class ModernVideoConverterApp(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.conversion_thread = None
        self.last_action_mode = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Jeel - Convertidor y Compresor de Videos")
        self.setMinimumSize(650, 500)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Título
        title = QLabel("🎬 Jeel")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("Convierte y comprime videos")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(subtitle)

        # Archivos
        self.input_display, self.input_btn = self._file_row("Video de entrada", layout)
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_display, self.output_btn = self._file_row("Video de salida", layout, save=True)
        self.output_btn.clicked.connect(self.select_output_file)

        # Selector de calidad (SOLO para compresión)
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Calidad de compresión:")
        quality_label.setFont(QFont("Segoe UI", 10))
        quality_label.setStyleSheet("color: #DDDDDD;")
        quality_layout.addWidget(quality_label)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Alta Calidad", "Balanceado", "Compresión", "Extrema"])
        self.quality_combo.setCurrentText("Balanceado")
        self.quality_combo.setStyleSheet("""
            QComboBox {
                padding: 8px; background-color: #2C2C2C; color: #E0E0E0;
                border-radius: 6px; border: 1px solid #555555;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { 
                background-color: #2C2C2C; color: #E0E0E0;
                selection-background-color: #3498DB;
            }
        """)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        layout.addLayout(quality_layout)

        # Botones acción (usando CustomButton)
        action_layout = QHBoxLayout()
        layout.addLayout(action_layout)

        self.convert_btn = MyButton("🔄 Convertir a MP4", "#3498DB", "#FFFFFF")
        self.compress_btn = MyButton("📦 Comprimir", "#27AE60", "#FFFFFF")
        self.cancel_btn = MyButton("❌ Cancelar", "#E74C3C", "#FFFFFF")

        action_layout.addWidget(self.convert_btn)
        action_layout.addWidget(self.compress_btn)
        action_layout.addWidget(self.cancel_btn)

        self.cancel_btn.setVisible(False)

        # Conexiones
        self.convert_btn.clicked.connect(self.convert_to_mp4)
        self.compress_btn.clicked.connect(self.compress_video)
        self.cancel_btn.clicked.connect(self.cancel_conversion)

        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 14px;
                border-radius: 7px;
                background-color: #333333;
                color: #FFFFFF;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498DB;
                border-radius: 7px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Estado
        self.status_label = QLabel("Listo para convertir videos")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #AAAAAA; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Botón de información
        self.info_button = InfoButton(self)
        self.info_button.clicked.connect(self.show_about_dialog)
        # Posicionar el botón
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()  # Esto empuja el botón a la derecha
        bottom_layout.addWidget(self.info_button)
        layout.addLayout(bottom_layout)
    
    def show_about_dialog(self):
        """Muestra el diálogo de información"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def _file_row(self, label_text, parent_layout, save=False):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFont(QFont("Segoe UI", 10))
        label.setStyleSheet("color: #DDDDDD;")
        
        display = QLabel("Selecciona un archivo..." if not save else "Selecciona destino...")
        display.setStyleSheet("""
            QLabel {
                padding: 8px; background-color: #2C2C2C; color: #888888;
                border-radius: 6px;
            }
        """)
        display.setMinimumHeight(35)

        # Aquí ya usamos tu botón personalizado
        btn = MyButton("Examinar" if not save else "Guardar como", "#555555", "#FFFFFF")

        layout.addWidget(label)
        layout.addWidget(display, 1)
        layout.addWidget(btn)
        parent_layout.addLayout(layout)
        
        return display, btn

    # --- Funciones de selección ---
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar video", str(Path.home()),
                                                   "Videos (*.mp4 *.webm *.mov *.mkv *.avi);;Todos (*.*)")
        if file_path:
            self.input_display.setText(file_path)
            self.input_display.setStyleSheet("padding: 8px; background-color: #2C2C2C; color: #E0E0E0; border-radius: 6px;")

    def select_output_file(self):
        default_name = str(Path.home() / "converted_video.mp4")
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar video como", default_name,
                                                   "Archivos MP4 (*.mp4);;Todos (*.*)")
        if file_path:
            self.output_display.setText(file_path)
            self.output_display.setStyleSheet("padding: 8px; background-color: #2C2C2C; color: #E0E0E0; border-radius: 6px;")

    # --- Validaciones ---
    def validate_inputs(self):
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        if not input_file or not output_file:
            QMessageBox.warning(self, "Advertencia", "Selecciona el video de entrada y salida")
            return False
        if not Path(input_file).exists():
            QMessageBox.warning(self, "Advertencia", "El archivo de entrada no existe")
            return False
        return True

    def set_ui_processing(self, processing):
        self.convert_btn.setVisible(not processing)
        self.compress_btn.setVisible(not processing)
        self.cancel_btn.setVisible(processing)
        self.input_btn.setDisabled(processing)
        self.output_btn.setDisabled(processing)
        self.progress_bar.setVisible(processing)

    def cancel_conversion(self):
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.status_label.setText("Cancelando conversión...")
            self.convert_btn.setEnabled(False)
            self.compress_btn.setEnabled(False)

    # --- Conversión ---
    def convert_to_mp4(self):
        if not self.validate_inputs(): return
        self.last_action_mode = 'convert'
        output_file = str(Path(self.output_display.text()).with_suffix('.mp4'))
        self.output_display.setText(output_file)
        
        # Mostrar información sobre el modo de conversión
        self.status_label.setText("Convirtiendo a MP4 (sin compresión)...")
        self.start_conversion('convert')

    def compress_video(self):
        if not self.validate_inputs(): return
        self.last_action_mode = 'compress'
        input_ext = Path(self.input_display.text()).suffix
        output_file = str(Path(self.output_display.text()).with_suffix(input_ext))
        self.output_display.setText(output_file)
        
        # Mostrar calidad seleccionada
        calidad = self.quality_combo.currentText()
        self.status_label.setText(f"Comprimiendo con calidad: {calidad}...")
        self.start_conversion('compress')

    def start_conversion(self, mode):
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        
        # Asegurar extensión correcta
        if mode == 'convert':
            output_file = str(Path(output_file).with_suffix('.mp4'))
        else:
            output_file = str(Path(output_file).with_suffix(Path(input_file).suffix))
        
        self.output_display.setText(output_file)
        self.set_ui_processing(True)
        self.progress_bar.setValue(0)

        # Mapear calidad seleccionada (SOLO para compresión)
        quality_map = {
            "Alta Calidad": "alta_calidad",
            "Balanceado": "balanceado", 
            "Compresión": "compresion",
            "Extrema": "extrema"
        }
        
        # Para conversión usar "balanceado" como default (aunque no se usa en conversión)
        quality_preset = quality_map.get(self.quality_combo.currentText(), "balanceado")
        
        self.conversion_thread = ConversionThread(input_file, output_file, mode, quality_preset)
        self.conversion_thread.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_thread.finished_signal.connect(self.conversion_finished)
        self.conversion_thread.start()

    def conversion_finished(self, success, message):
        self.set_ui_processing(False)
        if success:
            QMessageBox.information(self, "Éxito", message)
            self.status_label.setText("Proceso completado exitosamente")
            self.progress_bar.setValue(100)
        else:
            if "cancelada" not in message.lower():
                QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Listo para convertir videos")
            self.progress_bar.setValue(0)