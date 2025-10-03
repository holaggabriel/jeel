import sys
import subprocess
import re
import shlex
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox
from widgets.my_button import MyButton

# --- Excepciones personalizadas ---
class FFmpegNotFoundError(Exception):
    pass

class CorruptedFileError(Exception):
    pass

class ConversionError(Exception):
    pass

# --- Thread para conversión ---
class ConversionThread(QThread):
    progress_updated = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, input_file, output_file, mode, quality_preset="balanceado"):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.mode = mode
        self.quality_preset = quality_preset
        self._is_running = True
        self._ffmpeg_process = None

    def _check_ffmpeg_availability(self):
        """Verifica que ffmpeg y ffprobe estén disponibles"""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise FFmpegNotFoundError("FFmpeg no encontrado. Instálalo y agrégalo al PATH")

    def _validate_input_file(self):
        """Valida que el archivo de entrada exista y sea válido"""
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"El archivo no existe: {self.input_file}")
        
        if os.path.getsize(self.input_file) == 0:
            raise CorruptedFileError("El archivo de entrada está vacío")
        
        # Verificar con ffprobe que sea un video válido
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                self.input_file
            ], capture_output=True, text=True, check=True, timeout=10)
            
            if not result.stdout.strip():
                raise CorruptedFileError("El archivo no contiene stream de video válido")
                
        except subprocess.TimeoutExpired:
            raise CorruptedFileError("Timeout al validar el archivo de video")
        except subprocess.CalledProcessError:
            raise CorruptedFileError("El archivo no es un video válido o está corrupto")

    def _get_quality_settings(self):
        """Obtiene los ajustes de calidad según el preset seleccionado"""
        quality_presets = {
            "alta_calidad": {"crf": "18", "preset": "slow", "audio_bitrate": "192k"},
            "balanceado": {"crf": "23", "preset": "medium", "audio_bitrate": "128k"},
            "compresion": {"crf": "28", "preset": "fast", "audio_bitrate": "96k"},
            "extrema": {"crf": "32", "preset": "veryfast", "audio_bitrate": "64k"}
        }
        
        return quality_presets.get(self.quality_preset, quality_presets["balanceado"])

    def _get_ffmpeg_command(self):
        """Construye el comando ffmpeg con las rutas escapadas correctamente"""
        
        if self.mode == 'convert':
            # SOLO CONVERSIÓN - SIN COMPRIMIR (copy codecs)
            return [
                "ffmpeg", "-i", shlex.quote(self.input_file),
                "-c:v", "copy", "-c:a", "copy",  # Copiar sin re-codificar
                shlex.quote(self.output_file), "-y"
            ]
        
        # MODO COMPRESIÓN - usar ajustes de calidad
        quality_settings = self._get_quality_settings()
        
        codec_configs = {
            '.mp4': {"vcodec": "libx264", "acodec": "aac"},
            '.webm': {"vcodec": "libvpx-vp9", "acodec": "libopus"},
            '.mov': {"vcodec": "libx264", "acodec": "aac"},
            '.mkv': {"vcodec": "libx264", "acodec": "aac"},
            '.avi': {"vcodec": "mpeg4", "qscale": "5", "acodec": "mp3"}
        }
        
        output_ext = Path(self.output_file).suffix.lower()
        config = codec_configs.get(output_ext, codec_configs['.mp4'])
        
        cmd = ["ffmpeg", "-i", shlex.quote(self.input_file)]
        
        if 'qscale' in config:
            cmd.extend(["-c:v", config["vcodec"], "-qscale:v", config["qscale"]])
        else:
            cmd.extend(["-c:v", config["vcodec"], "-crf", quality_settings["crf"]])
            if quality_settings["preset"]:
                cmd.extend(["-preset", quality_settings["preset"]])
        
        cmd.extend([
            "-c:a", config["acodec"], "-b:a", quality_settings["audio_bitrate"],
            shlex.quote(self.output_file), "-y"
        ])
        
        return cmd

    def _parse_duration(self, duration_str):
        """Parsea la duración del formato HH:MM:SS.ms a segundos"""
        try:
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                sec_parts = seconds.split('.')
                sec = float(sec_parts[0])
                if len(sec_parts) > 1:
                    sec += float(f"0.{sec_parts[1]}")
                return float(hours) * 3600 + float(minutes) * 60 + sec
            return 0
        except Exception:
            return 0

    def _parse_progress(self, line, total_duration):
        """Parsea el progreso de la salida de ffmpeg"""
        match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
        if match and total_duration > 0:
            current_time = self._parse_duration(match.group(1))
            progress = int((current_time / total_duration) * 100)
            return min(progress, 100)
        return None

    def _check_disk_space(self, required_bytes):
        """Verifica que haya espacio suficiente en disco"""
        output_path = Path(self.output_file)
        if output_path.exists():
            required_bytes -= output_path.stat().st_size
            
        try:
            disk_usage = os.path.splitdrive(self.output_file)[0] + os.path.sep
            free_space = os.path.getfree(disk_usage)
            if free_space < required_bytes * 1.1:  # 10% de margen
                raise ConversionError(f"Espacio en disco insuficiente. Se requieren {required_bytes // (1024*1024)}MB")
        except Exception:
            # Si no se puede verificar el espacio, continuar con advertencia
            pass

    def run(self):
        try:
            # Validaciones previas
            self._check_ffmpeg_availability()
            self._validate_input_file()
            
            # Verificar espacio en disco (estimado: 2x tamaño original)
            input_size = os.path.getsize(self.input_file)
            self._check_disk_space(input_size * 2)

            cmd = self._get_ffmpeg_command()
            
            # Obtener duración total del video
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", self.input_file],
                    capture_output=True, text=True, check=True, timeout=30
                )
                total_duration = float(result.stdout.strip())
            except (subprocess.TimeoutExpired, ValueError, subprocess.CalledProcessError):
                total_duration = 0

            # Ejecutar conversión
            self._ffmpeg_process = subprocess.Popen(
                cmd, 
                stderr=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                universal_newlines=True,
                bufsize=1
            )
            
            while self._is_running and self._ffmpeg_process.poll() is None:
                line = self._ffmpeg_process.stderr.readline()
                if not line:
                    break
                if total_duration > 0:
                    progress = self._parse_progress(line, total_duration)
                    if progress is not None:
                        self.progress_updated.emit(progress)
            
            # Esperar a que termine el proceso si no fue cancelado
            if self._is_running:
                self._ffmpeg_process.wait()
                
            if self._is_running and self._ffmpeg_process.returncode == 0:
                self.progress_updated.emit(100)
                self.finished_signal.emit(True, f"Proceso completado!\n{self.output_file}")
            elif self._is_running:
                raise ConversionError(f"Error en FFmpeg. Código: {self._ffmpeg_process.returncode}")
            else:
                self.finished_signal.emit(False, "Conversión cancelada por el usuario")
                
        except FFmpegNotFoundError as e:
            self.finished_signal.emit(False, f"Error: {str(e)}")
        except CorruptedFileError as e:
            self.finished_signal.emit(False, f"Error en archivo: {str(e)}")
        except ConversionError as e:
            self.finished_signal.emit(False, f"Error en conversión: {str(e)}")
        except subprocess.TimeoutExpired:
            self.finished_signal.emit(False, "Timeout: El proceso tardó demasiado en responder")
        except Exception as e:
            self.finished_signal.emit(False, f"Error inesperado: {str(e)}")

    def stop(self):
        """Detiene la conversión de manera segura"""
        self._is_running = False
        if self._ffmpeg_process and self._ffmpeg_process.poll() is None:
            # Enviar señal de terminación a ffmpeg
            self._ffmpeg_process.terminate()
            try:
                # Esperar máximo 5 segundos para que termine graceful
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Forzar kill si no responde
                self._ffmpeg_process.kill()
                self._ffmpeg_process.wait()

# --- UI moderna ---
class ModernVideoConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conversion_thread = None
        self.last_action_mode = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("🎬 Video Converter Pro")
        self.setMinimumSize(650, 500)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # Título
        title = QLabel("🎬 Video Converter Pro")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("Convierte y comprime videos con calidad profesional")
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

# --- Main ---
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("QMainWindow, QWidget { background-color: #1E1E1E; color: #FFFFFF; }")
    window = ModernVideoConverterApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()