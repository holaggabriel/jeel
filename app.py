import sys
import subprocess
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

# --- Thread para conversión ---
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
        if self.mode == 'convert':
            return [
                "ffmpeg", "-i", self.input_file,
                "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                "-c:a", "aac", "-b:a", "192k", self.output_file, "-y"
            ]
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
        if 'qscale' in config:
            cmd.extend(["-c:v", config["vcodec"], "-qscale:v", config["qscale"]])
        else:
            cmd.extend(["-c:v", config["vcodec"], "-crf", config["crf"]])
            if config["preset"]:
                cmd.extend(["-preset", config["preset"]])
        cmd.extend(["-c:a", config["acodec"], "-b:a", config["audio_bitrate"], self.output_file, "-y"])
        return cmd

    def _parse_duration(self, duration_str):
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
        except:
            return 0

    def _parse_progress(self, line, total_duration):
        match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
        if match and total_duration > 0:
            current_time = self._parse_duration(match.group(1))
            progress = int((current_time / total_duration) * 100)
            return min(progress, 100)
        return None

    def run(self):
        try:
            cmd = self._get_ffmpeg_command()
            # Obtener duración
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", self.input_file],
                    capture_output=True, text=True, check=True
                )
                total_duration = float(result.stdout.strip())
            except:
                total_duration = 0

            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
            while self._is_running:
                line = process.stderr.readline()
                if not line:
                    break
                if total_duration > 0:
                    progress = self._parse_progress(line, total_duration)
                    if progress is not None:
                        self.progress_updated.emit(progress)
            process.wait()
            if process.returncode == 0:
                self.progress_updated.emit(100)
                self.finished_signal.emit(True, f"Proceso completado!\n{self.output_file}")
            else:
                self.finished_signal.emit(False, f"Error en el proceso. Código: {process.returncode}")
        except Exception as e:
            self.finished_signal.emit(False, f"Error: {str(e)}")

    def stop(self):
        self._is_running = False

# --- UI moderna ---
class ModernVideoConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conversion_thread = None
        self.last_action_mode = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("🎬 Video Converter Pro")
        self.setMinimumSize(650, 450)
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

        # Botones acción
        action_layout = QHBoxLayout()
        layout.addLayout(action_layout)
        self.convert_btn = QPushButton("🎥 Convertir a MP4")
        self.compress_btn = QPushButton("📦 Comprimir")
        self.cancel_btn = QPushButton("❌ Cancelar")
        for btn, color in [(self.convert_btn, "#3498DB"), (self.compress_btn, "#27AE60"), (self.cancel_btn, "#E74C3C")]:
            btn.setStyleSheet(self._btn_style(color))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_layout.addWidget(btn)
        self.cancel_btn.setVisible(False)
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
        btn = QPushButton("Examinar" if not save else "Guardar como")
        btn.setStyleSheet(self._btn_style("#555555"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(label)
        layout.addWidget(display, 1)
        layout.addWidget(btn)
        parent_layout.addLayout(layout)
        return display, btn

    def _btn_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """

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
            self.conversion_thread.terminate()
            self.conversion_thread.wait()
            self.status_label.setText("Conversión cancelada")
            self.set_ui_processing(False)

    # --- Conversión ---
    def convert_to_mp4(self):
        if not self.validate_inputs(): return
        self.last_action_mode = 'convert'
        output_file = str(Path(self.output_display.text()).with_suffix('.mp4'))
        self.output_display.setText(output_file)
        self.start_conversion('convert')

    def compress_video(self):
        if not self.validate_inputs(): return
        self.last_action_mode = 'compress'
        input_ext = Path(self.input_display.text()).suffix
        output_file = str(Path(self.output_display.text()).with_suffix(input_ext))
        self.output_display.setText(output_file)
        self.start_conversion('compress')

    def start_conversion(self, mode):
        input_file = self.input_display.text()
        output_file = self.output_display.text()
        if mode == 'convert':
            output_file = str(Path(output_file).with_suffix('.mp4'))
        else:
            output_file = str(Path(output_file).with_suffix(Path(input_file).suffix))
        self.output_display.setText(output_file)
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
            QMessageBox.information(self, "Éxito", message)
            self.status_label.setText("Proceso completado exitosamente")
            self.progress_bar.setValue(100)
        else:
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Error en el proceso")
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