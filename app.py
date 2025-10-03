import sys
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QProgressBar, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QAction, QIcon
from pathlib import Path

class ConversionThread(QThread):
    progress_updated = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, input_file, output_file, mode):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.mode = mode  # 'convert' or 'compress'
    
    def run(self):
        try:
            if self.mode == 'convert':
                # CONVERTIR a MP4 (igual que antes)
                cmd = [
                    "ffmpeg", "-i", self.input_file,
                    "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                    "-c:a", "aac", "-b:a", "192k", self.output_file
                ]
            else:  # COMPRIMIR (mantener formato original)
                # Obtener la extensión del archivo de salida
                output_ext = Path(self.output_file).suffix.lower()
                
                # Configurar codecs según el formato de salida
                if output_ext == '.mp4':
                    cmd = [
                        "ffmpeg", "-i", self.input_file,
                        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                        "-c:a", "aac", "-b:a", "128k", self.output_file
                    ]
                elif output_ext == '.webm':
                    cmd = [
                        "ffmpeg", "-i", self.input_file,
                        "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
                        "-c:a", "libopus", "-b:a", "96k", self.output_file
                    ]
                elif output_ext == '.mov':
                    cmd = [
                        "ffmpeg", "-i", self.input_file,
                        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                        "-c:a", "aac", "-b:a", "128k", self.output_file
                    ]
                elif output_ext == '.mkv':
                    cmd = [
                        "ffmpeg", "-i", self.input_file,
                        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                        "-c:a", "aac", "-b:a", "128k", self.output_file
                    ]
                elif output_ext == '.avi':
                    cmd = [
                        "ffmpeg", "-i", self.input_file,
                        "-c:v", "mpeg4", "-qscale:v", "5",
                        "-c:a", "mp3", "-b:a", "128k", self.output_file
                    ]
                else:
                    # Por defecto, usar H.264
                    cmd = [
                        "ffmpeg", "-i", self.input_file,
                        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                        "-c:a", "aac", "-b:a", "128k", self.output_file
                    ]
            
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
            
            # Simular progreso
            for i in range(101):
                self.progress_updated.emit(i)
                self.msleep(50)
                
            process.wait()
            
            if process.returncode == 0:
                self.finished_signal.emit(True, f"Proceso completado exitosamente!\n{self.output_file}")
            else:
                error_output = process.stderr.read()
                self.finished_signal.emit(False, f"Error en el proceso. Código: {process.returncode}\n{error_output}")
                
        except Exception as e:
            self.finished_signal.emit(False, f"Error: {str(e)}")

class VideoConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.conversion_thread = None
    
    def initUI(self):
        self.setWindowTitle("Video Converter Pro - PyQt6")
        self.setMinimumSize(650, 450)
        
        # Crear menú
        self.create_menu()
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Título
        title = QLabel("🎬 Video Converter Pro")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #E0E0E0; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Subtítulo
        subtitle = QLabel("Convierte y comprime videos con calidad profesional")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #B0B0B0; margin-bottom: 20px;")
        layout.addWidget(subtitle)
        
        # Grupo de entrada/salida
        io_group = QGroupBox("Configuración de Archivos")
        io_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 10px;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 8px;
                background-color: #2D2D2D;
            }
        """)
        io_layout = QVBoxLayout(io_group)
        
        # Entrada de video
        input_layout = QHBoxLayout()
        self.input_label = QLabel("Video de entrada:")
        self.input_label.setFixedWidth(120)
        self.input_label.setFont(QFont("Segoe UI", 10))
        self.input_label.setStyleSheet("color: #CCCCCC;")
        
        self.input_display = QLabel("Selecciona un archivo de video...")
        self.input_display.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #404040;
                color: #888888;
                border: 1px solid #555555;
                border-radius: 4px;
                min-height: 15px;
            }
        """)
        self.input_display.setMinimumHeight(35)
        
        self.input_browse = QPushButton("Examinar")
        self.input_browse.setStyleSheet(self.get_button_style("#3498DB"))
        self.input_browse.clicked.connect(self.select_input_file)
        
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_display)
        input_layout.addWidget(self.input_browse)
        io_layout.addLayout(input_layout)
        
        # Salida de video
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Video de salida:")
        self.output_label.setFixedWidth(120)
        self.output_label.setFont(QFont("Segoe UI", 10))
        self.output_label.setStyleSheet("color: #CCCCCC;")
        
        self.output_display = QLabel("Selecciona destino con 'Guardar como'...")
        self.output_display.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #404040;
                color: #888888;
                border: 1px solid #555555;
                border-radius: 4px;
                min-height: 15px;
            }
        """)
        self.output_display.setMinimumHeight(35)
        
        self.output_browse = QPushButton("Guardar como")
        self.output_browse.setStyleSheet(self.get_button_style("#3498DB"))
        self.output_browse.clicked.connect(self.select_output_file)
        
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_display)
        output_layout.addWidget(self.output_browse)
        io_layout.addLayout(output_layout)
        
        layout.addWidget(io_group)
        
        # Grupo de acciones
        action_group = QGroupBox("Acciones")
        action_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 10px;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 8px;
                background-color: #2D2D2D;
            }
        """)
        action_layout = QHBoxLayout(action_group)
        
        # Botones de acción
        self.convert_btn = QPushButton("🎥 Convertir a MP4")
        self.convert_btn.setStyleSheet(self.get_button_style("#2E86AB", hover="#1B6B93"))
        self.convert_btn.clicked.connect(self.convert_to_mp4)
        self.convert_btn.setToolTip("Convierte cualquier formato de video a MP4 con alta calidad")
        
        self.compress_btn = QPushButton("📦 Comprimir Video")
        self.compress_btn.setStyleSheet(self.get_button_style("#28A745", hover="#1E7E34"))
        self.compress_btn.clicked.connect(self.compress_video)
        self.compress_btn.setToolTip("Comprime el video manteniendo el mismo formato (reduce tamaño sin cambiar formato)")
        
        action_layout.addWidget(self.convert_btn)
        action_layout.addWidget(self.compress_btn)
        layout.addWidget(action_group)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 5px;
                text-align: center;
                height: 15px;
                background-color: #404040;
                color: #E0E0E0;
            }
            QProgressBar::chunk {
                background-color: #3498DB;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Estado
        self.status_label = QLabel("Listo para convertir videos")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #B0B0B0; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        # Espacio flexible
        layout.addStretch()
    
    def get_button_style(self, color, hover=None):
        if hover is None:
            hover = color
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:disabled {{
                background-color: #555555;
                color: #888888;
            }}
        """
    
    def create_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border-bottom: 1px solid #555555;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background-color: #404040;
            }
            QMenu {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border: 1px solid #555555;
            }
            QMenu::item {
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #404040;
            }
        """)
        
        # Menú Archivo
        file_menu = menubar.addMenu('&Archivo')
        
        new_action = QAction('&Nuevo', self)
        new_action.setShortcut('Ctrl+N')
        file_menu.addAction(new_action)
        
        open_action = QAction('&Abrir', self)
        open_action.setShortcut('Ctrl+O')
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('&Salir', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menú Ayuda
        help_menu = menubar.addMenu('&Ayuda')
        
        about_action = QAction('&Acerca de', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def show_about(self):
        about_box = QMessageBox(self)
        about_box.setWindowTitle("Acerca de Video Converter Pro")
        about_box.setText("Video Converter Pro v1.0\n\n"
                         "Una aplicación profesional para conversión y compresión de videos.\n"
                         "Desarrollado con PyQt6 y FFmpeg.")
        about_box.setStyleSheet("""
            QMessageBox {
                background-color: #2D2D2D;
                color: #E0E0E0;
            }
            QMessageBox QLabel {
                color: #E0E0E0;
            }
            QMessageBox QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        about_box.exec()
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar video",
            str(Path.home()),
            "Archivos de video (*.mp4 *.webm *.mov *.mkv *.avi);;Todos los archivos (*.*)"
        )
        if file_path:
            self.input_display.setText(file_path)
            self.input_display.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    background-color: #404040;
                    color: #E0E0E0;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    min-height: 15px;
                }
            """)
    
    def select_output_file(self):
        input_file = self.input_display.text()
        
        # Si hay un archivo de entrada, sugerir la misma extensión
        if input_file and input_file != "Selecciona un archivo de video...":
            input_ext = Path(input_file).suffix
            default_name = str(Path.home() / f"compressed_video{input_ext}")
        else:
            default_name = str(Path.home() / "converted_video.mp4")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar video como",
            default_name,
            "Archivos de video (*.mp4 *.webm *.mov *.mkv *.avi);;Todos los archivos (*.*)"
        )
        if file_path:
            self.output_display.setText(file_path)
            self.output_display.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    background-color: #404040;
                    color: #E0E0E0;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    min-height: 15px;
                }
            """)
    
    def validate_inputs(self):
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        
        if not input_file or input_file == "Selecciona un archivo de video..." or not output_file or output_file == "Selecciona destino con 'Guardar como'...":
            QMessageBox.warning(self, "Advertencia", "Selecciona el video de entrada y salida")
            return False
        
        if not Path(input_file).exists():
            QMessageBox.warning(self, "Advertencia", "El archivo de entrada no existe")
            return False
            
        return True
    
    def set_ui_processing(self, processing):
        self.convert_btn.setDisabled(processing)
        self.compress_btn.setDisabled(processing)
        self.input_browse.setDisabled(processing)
        self.output_browse.setDisabled(processing)
        self.progress_bar.setVisible(processing)
    
    def convert_to_mp4(self):
        """Convierte cualquier formato de video a MP4 con alta calidad"""
        if self.validate_inputs():
            self.start_conversion('convert')
    
    def compress_video(self):
        """Comprime el video manteniendo el formato original"""
        if not self.validate_inputs():
            return
        
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        
        # Validar que los formatos de entrada y salida sean iguales
        input_ext = Path(input_file).suffix.lower()
        output_ext = Path(output_file).suffix.lower()
        
        if input_ext != output_ext:
            reply = QMessageBox.question(
                self, 
                "Confirmar compresión", 
                f"Estás cambiando el formato de {input_ext} a {output_ext}. "
                f"¿Deseas comprimir manteniendo el formato original ({input_ext})?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Cambiar la extensión de salida para que coincida con la entrada
                new_output = Path(output_file).with_suffix(input_ext)
                self.output_display.setText(str(new_output))
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        self.start_conversion('compress')
    
    def start_conversion(self, mode):
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        
        self.set_ui_processing(True)
        self.status_label.setText("Procesando... Por favor espera.")
        self.progress_bar.setValue(0)
        
        self.conversion_thread = ConversionThread(input_file, output_file, mode)
        self.conversion_thread.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_thread.finished_signal.connect(self.conversion_finished)
        self.conversion_thread.start()
    
    def conversion_finished(self, success, message):
        self.set_ui_processing(False)
        
        if success:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Éxito")
            msg.setText(message)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2D2D2D;
                    color: #E0E0E0;
                }
                QMessageBox QLabel {
                    color: #E0E0E0;
                }
                QMessageBox QPushButton {
                    background-color: #27AE60;
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background-color: #219653;
                }
            """)
            msg.exec()
            self.status_label.setText("Proceso completado exitosamente")
            self.progress_bar.setValue(100)
        else:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Error")
            msg.setText(message)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2D2D2D;
                    color: #E0E0E0;
                }
                QMessageBox QLabel {
                    color: #E0E0E0;
                }
                QMessageBox QPushButton {
                    background-color: #E74C3C;
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background-color: #C0392B;
                }
            """)
            msg.exec()
            self.status_label.setText("Error en el proceso")
            self.progress_bar.setValue(0)

def main():
    app = QApplication(sys.argv)
    
    # Establecer estilo moderno
    app.setStyle('Fusion')
    
    # Establecer estilo de aplicación con tema oscuro
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1E1E1E;
        }
        QWidget {
            background-color: #1E1E1E;
            color: #E0E0E0;
        }
        QGroupBox {
            margin-top: 10px;
        }
        QMessageBox {
            background-color: #2D2D2D;
            color: #E0E0E0;
        }
        QMessageBox QLabel {
            color: #E0E0E0;
        }
    """)
    
    window = VideoConverterApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()