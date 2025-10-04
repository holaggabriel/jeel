import os
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
from .ffmpeg_utils import (
    check_ffmpeg_availability, validate_input_file, check_disk_space,
    get_ffmpeg_command, get_video_duration, parse_progress
)
from .exceptions import ConversionError
from pathlib import Path

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

    def run(self):
        try:
            # Validaciones previas
            check_ffmpeg_availability()
            validate_input_file(self.input_file)
            
            # Verificar espacio en disco (estimado: 2x tamaño original)
            input_size = os.path.getsize(self.input_file)
            check_disk_space(self.output_file, input_size * 2)

            # Normalizar rutas para Windows/Linux
            self.input_file = str(Path(self.input_file).resolve().as_posix())
            self.output_file = str(Path(self.output_file).resolve().as_posix())

            # Log para verificar rutas
            print("Resolved input file:", self.input_file)
            print("Resolved output file:", self.output_file)

            # Construir comando FFmpeg con rutas normalizadas
            cmd = get_ffmpeg_command(self.input_file, self.output_file, self.mode, self.quality_preset)

            # Obtener duración total del video
            total_duration = get_video_duration(self.input_file)

            # Ejecutar conversión
            self._ffmpeg_process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,           
                encoding="utf-8",   
                errors="replace",    
                bufsize=1
            )
            
            while self._is_running and self._ffmpeg_process.poll() is None:
                line = self._ffmpeg_process.stderr.readline()
                if not line:
                    break
                if total_duration > 0:
                    progress = parse_progress(line, total_duration)
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
                
        except Exception as e:
            error_message = str(e)
            self.finished_signal.emit(False, error_message)
    
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