import sys
import subprocess
import re
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QMessageBox,
                             QProgressBar, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

class ConversionThread(QThread):
    progress_updated = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, input_file, output_file, mode):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.mode = mode
        self._is_running = True
    
    def _get_ffmpeg_command(self):
        """Genera el comando FFmpeg según el modo y formato"""
        if self.mode == 'convert':
            return [
                "ffmpeg", "-i", self.input_file,
                "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                "-c:a", "aac", "-b:a", "192k", self.output_file, "-y"
            ]
        
        # Configuraciones para compresión por formato
        codec_configs = {
            '.mp4': {"vcodec": "libx264", "crf": "23", "preset": "medium", "acodec": "aac", "audio_bitrate": "128k"},
            '.webm': {"vcodec": "libvpx-vp9", "crf": "30", "preset": "", "acodec": "libopus", "audio_bitrate": "96k"},
            '.mov': {"vcodec": "libx264", "crf": "23", "preset": "medium", "acodec": "aac", "audio_bitrate": "128k"},
            '.mkv': {"vcodec": "libx264", "crf": "23", "preset": "medium", "acodec": "aac", "audio_bitrate": "128k"},
            '.avi': {"vcodec": "mpeg4", "qscale": "5", "preset": "", "acodec": "mp3", "audio_bitrate": "128k"}
        }
        
        output_ext = Path(self.output_file).suffix.lower()
        config = codec_configs.get(output_ext, codec_configs['.mp4'])
        
        cmd = ["ffmpeg", "-i", self.input_file]
        
        if 'qscale' in config:  # Para AVI
            cmd.extend(["-c:v", config["vcodec"], "-qscale:v", config["qscale"]])
        else:
            cmd.extend(["-c:v", config["vcodec"], "-crf", config["crf"]])
            if config["preset"]:
                cmd.extend(["-preset", config["preset"]])
        
        cmd.extend(["-c:a", config["acodec"], "-b:a", config["audio_bitrate"], self.output_file, "-y"])
        
        return cmd

    def _parse_duration(self, duration_str):
        """Convierte string de duración (hh:mm:ss.ms) a segundos totales"""
        try:
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                seconds_parts = seconds.split('.')
                sec = float(seconds_parts[0])
                if len(seconds_parts) > 1:
                    sec += float(f"0.{seconds_parts[1]}")
                return float(hours) * 3600 + float(minutes) * 60 + sec
            return 0
        except:
            return 0

    def _parse_progress(self, line, total_duration):
        """Parsea la línea de progreso de FFmpeg y retorna el porcentaje"""
        # Buscar el tiempo actual en el formato time=hh:mm:ss.ms
        time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
        if time_match and total_duration > 0:
            current_time = self._parse_duration(time_match.group(1))
            progress = int((current_time / total_duration) * 100)
            return min(progress, 100)
        return None

    def run(self):
        try:
            cmd = self._get_ffmpeg_command()
            
            # Primero obtener la duración del video
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", 
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                self.input_file
            ]
            
            total_duration = 0
            try:
                result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                total_duration = float(result.stdout.strip())
            except:
                # Si no podemos obtener la duración, usar progreso simulado
                total_duration = 0

            process = subprocess.Popen(
                cmd, 
                stderr=subprocess.PIPE, 
                stdout=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # Monitorear el progreso en tiempo real
            while self._is_running:
                line = process.stderr.readline()
                if not line:
                    break
                    
                if total_duration > 0:
                    progress = self._parse_progress(line, total_duration)
                    if progress is not None:
                        self.progress_updated.emit(progress)
                else:
                    # Progreso simulado como fallback
                    current_progress = self.progress_bar.value() if hasattr(self, 'progress_bar') else 0
                    if current_progress < 90:
                        self.progress_updated.emit(current_progress + 1)

            process.wait()
            
            if process.returncode == 0:
                self.progress_updated.emit(100)
                self.finished_signal.emit(True, f"Proceso completado exitosamente!\n{self.output_file}")
            else:
                self.finished_signal.emit(False, f"Error en el proceso. Código: {process.returncode}")

        except Exception as e:
            self.finished_signal.emit(False, f"Error: {str(e)}")

    def stop(self):
        """Detener el proceso de conversión"""
        self._is_running = False

class VideoConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conversion_thread = None
        self.last_action_mode = None  # Para trackear el último modo usado
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Video Converter Pro - PyQt6")
        self.setMinimumSize(650, 450)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Crear elementos de la UI
        self._create_title_section(layout)
        self._create_file_section(layout)
        self._create_action_section(layout)
        self._create_progress_section(layout)
        
        # Espacio flexible
        layout.addStretch()
    
    def _create_title_section(self, layout):
        """Crea la sección de título"""
        title = QLabel("🎬 Video Converter Pro")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #E0E0E0; margin-bottom: 10px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Convierte y comprime videos con calidad profesional")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #B0B0B0; margin-bottom: 20px;")
        layout.addWidget(subtitle)
    
    def _create_styled_group(self, title):
        """Crea un grupo con estilo consistente"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; font-size: 12px; margin-top: 10px;
                color: #CCCCCC; border: 1px solid #555555;
                border-radius: 6px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; padding: 0 8px;
                background-color: #2D2D2D;
            }
        """)
        return group
    
    def _create_file_row(self, label_text, display_text, button_text, button_slot):
        """Crea una fila para selección de archivos"""
        layout = QHBoxLayout()
        
        label = QLabel(label_text)
        label.setFixedWidth(120)
        label.setFont(QFont("Segoe UI", 10))
        label.setStyleSheet("color: #CCCCCC;")
        
        display = QLabel(display_text)
        display.setStyleSheet("""
            QLabel {
                padding: 8px; background-color: #404040; color: #888888;
                border: 1px solid #555555; border-radius: 4px; min-height: 15px;
            }
        """)
        display.setMinimumHeight(35)
        
        button = QPushButton(button_text)
        button.setStyleSheet(self._get_button_style("#3498DB"))
        button.clicked.connect(button_slot)
        
        layout.addWidget(label)
        layout.addWidget(display)
        layout.addWidget(button)
        
        return layout, display, button
    
    def _create_file_section(self, layout):
        """Crea la sección de selección de archivos"""
        io_group = self._create_styled_group("Configuración de Archivos")
        io_layout = QVBoxLayout(io_group)
        
        # Entrada de video
        input_layout, self.input_display, self.input_browse = self._create_file_row(
            "Video de entrada:", "Selecciona un archivo de video...", "Examinar", self.select_input_file
        )
        io_layout.addLayout(input_layout)
        
        # Salida de video
        output_layout, self.output_display, self.output_browse = self._create_file_row(
            "Video de salida:", "Selecciona destino con 'Guardar como'...", "Guardar como", self.select_output_file
        )
        io_layout.addLayout(output_layout)
        
        layout.addWidget(io_group)
    
    def _create_action_section(self, layout):
        """Crea la sección de botones de acción"""
        action_group = self._create_styled_group("Acciones")
        action_layout = QHBoxLayout(action_group)
        
        # Botones de acción
        self.convert_btn = QPushButton("🎥 Convertir a MP4")
        self.compress_btn = QPushButton("📦 Comprimir Video")
        self.cancel_btn = QPushButton("❌ Cancelar")
        
        for btn, color, hover, slot, tooltip, visible in [
            (self.convert_btn, "#2E86AB", "#1B6B93", self.convert_to_mp4, 
             "Convierte cualquier formato de video a MP4 (extensión .mp4 automática)", True),
            (self.compress_btn, "#28A745", "#1E7E34", self.compress_video,
             "Comprime el video manteniendo el mismo formato del archivo original", True),
            (self.cancel_btn, "#E74C3C", "#C0392B", self.cancel_conversion,
             "Cancela la conversión en curso", False)
        ]:
            btn.setStyleSheet(self._get_button_style(color, hover))
            btn.clicked.connect(slot)
            btn.setToolTip(tooltip)
            btn.setVisible(visible)
            action_layout.addWidget(btn)
        
        layout.addWidget(action_group)
    
    def _create_progress_section(self, layout):
        """Crea la sección de progreso y estado"""
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555; border-radius: 5px; text-align: center;
                height: 15px; background-color: #404040; color: #E0E0E0;
            }
            QProgressBar::chunk {
                background-color: #3498DB; border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Listo para convertir videos")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #B0B0B0; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.status_label)
    
    def _get_button_style(self, color, hover=None):
        """Retorna el estilo CSS para botones"""
        if hover is None:
            hover = color
        return f"""
            QPushButton {{
                background-color: {color}; color: white; border: none;
                padding: 10px 15px; border-radius: 5px;
                font-weight: bold; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{
                background-color: #555555; color: #888888;
            }}
        """
    
    def _update_display_style(self, display_widget):
        """Actualiza el estilo del display cuando tiene contenido válido"""
        display_widget.setStyleSheet("""
            QLabel {
                padding: 8px; background-color: #404040; color: #E0E0E0;
                border: 1px solid #555555; border-radius: 4px; min-height: 15px;
            }
        """)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar video", str(Path.home()),
            "Archivos de video (*.mp4 *.webm *.mov *.mkv *.avi);;Todos los archivos (*.*)"
        )
        if file_path:
            self.input_display.setText(file_path)
            self._update_display_style(self.input_display)
    
    def select_output_file(self):
        input_file = self.input_display.text()
        
        # Determinar la extensión por defecto basada en el último modo usado
        if self.last_action_mode == 'convert':
            default_ext = ".mp4"
        elif self.last_action_mode == 'compress':
            if input_file and input_file != "Selecciona un archivo de video...":
                default_ext = Path(input_file).suffix
            else:
                default_ext = ".mp4"
        else:
            default_ext = ".mp4"  # Por defecto
        
        default_name = str(Path.home() / f"converted_video{default_ext}")
        
        # Filtro dinámico basado en el modo
        if self.last_action_mode == 'convert':
            file_filter = "Archivos MP4 (*.mp4);;Todos los archivos (*.*)"
        else:
            file_filter = "Archivos de video (*.mp4 *.webm *.mov *.mkv *.avi);;Todos los archivos (*.*)"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar video como", default_name, file_filter
        )
        
        if file_path:
            # Asegurar la extensión correcta basada en el último modo
            if self.last_action_mode == 'convert':
                file_path = str(Path(file_path).with_suffix('.mp4'))
            elif self.last_action_mode == 'compress' and input_file and input_file != "Selecciona un archivo de video...":
                file_path = str(Path(file_path).with_suffix(Path(input_file).suffix))
            
            self.output_display.setText(file_path)
            self._update_display_style(self.output_display)
    
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
        """Habilita/deshabilita UI durante el procesamiento"""
        self.convert_btn.setVisible(not processing)
        self.compress_btn.setVisible(not processing)
        self.cancel_btn.setVisible(processing)
        self.input_browse.setDisabled(processing)
        self.output_browse.setDisabled(processing)
        self.progress_bar.setVisible(processing)

    def cancel_conversion(self):
        """Cancela la conversión en curso"""
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.conversion_thread.terminate()
            self.conversion_thread.wait()
            self.status_label.setText("Conversión cancelada")
            self.set_ui_processing(False)
    
    def convert_to_mp4(self):
        if self.validate_inputs():
            # Forzar extensión .mp4
            input_file = self.input_display.text()
            output_file = self.output_display.text()
            output_file_mp4 = str(Path(output_file).with_suffix('.mp4'))
            
            if output_file != output_file_mp4:
                self.output_display.setText(output_file_mp4)
                self._update_display_style(self.output_display)
            
            self.last_action_mode = 'convert'
            self.start_conversion('convert')
    
    def compress_video(self):
        if not self.validate_inputs():
            return
        
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        
        # Mantener la misma extensión que el archivo de entrada
        input_ext = Path(input_file).suffix.lower()
        output_file_same_ext = str(Path(output_file).with_suffix(input_ext))
        
        if output_file != output_file_same_ext:
            self.output_display.setText(output_file_same_ext)
            self._update_display_style(self.output_display)
        
        self.last_action_mode = 'compress'
        self.start_conversion('compress')
    
    def start_conversion(self, mode):
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        
        # Verificación final para asegurar la extensión correcta
        if mode == 'convert':
            output_file = str(Path(output_file).with_suffix('.mp4'))
        else:  # compress
            input_ext = Path(input_file).suffix
            output_file = str(Path(output_file).with_suffix(input_ext))
        
        # Actualizar la UI si cambió el nombre
        if output_file != self.output_display.text():
            self.output_display.setText(output_file)
            self._update_display_style(self.output_display)
        
        self.set_ui_processing(True)
        self.status_label.setText("Procesando... Por favor espera.")
        self.progress_bar.setValue(0)
        
        self.conversion_thread = ConversionThread(input_file, output_file, mode)
        self.conversion_thread.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_thread.finished_signal.connect(self.conversion_finished)
        self.conversion_thread.start()
    
    def _show_message(self, title, message, icon, button_color):
        """Muestra un mensaje modal con estilo"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(icon)
        msg.setStyleSheet(f"""
            QMessageBox {{
                background-color: #2D2D2D;
                color: #E0E0E0;
            }}
            QMessageBox QLabel {{
                color: #E0E0E0;
            }}
            QMessageBox QPushButton {{
                background-color: {button_color};
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QMessageBox QPushButton:hover {{
                background-color: #2980B9;
            }}
        """)
        msg.exec()
    
    def conversion_finished(self, success, message):
        self.set_ui_processing(False)
        
        if success:
            self._show_message("Éxito", message, QMessageBox.Icon.Information, "#27AE60")
            self.status_label.setText("Proceso completado exitosamente")
            self.progress_bar.setValue(100)
        else:
            self._show_message("Error", message, QMessageBox.Icon.Critical, "#E74C3C")
            self.status_label.setText("Error en el proceso")
            self.progress_bar.setValue(0)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Estilo de aplicación con tema oscuro
    app.setStyleSheet("""
        QMainWindow, QWidget { background-color: #1E1E1E; color: #E0E0E0; }
        QGroupBox { margin-top: 10px; }
    """)
    
    window = VideoConverterApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()