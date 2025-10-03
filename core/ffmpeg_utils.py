import os
import re
import subprocess
import shlex
from pathlib import Path
from .exceptions import FFmpegNotFoundError, CorruptedFileError, ConversionError

def check_ffmpeg_availability():
    """Verifica que ffmpeg y ffprobe estén disponibles"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise FFmpegNotFoundError("FFmpeg no encontrado. Instálalo y agrégalo al PATH")

def validate_input_file(input_file):
    """Valida que el archivo de entrada exista y sea válido"""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"El archivo no existe: {input_file}")
    
    if os.path.getsize(input_file) == 0:
        raise CorruptedFileError("El archivo de entrada está vacío")
    
    # Verificar con ffprobe que sea un video válido
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0",
            input_file
        ], capture_output=True, text=True, check=True, timeout=10)
        
        if not result.stdout.strip():
            raise CorruptedFileError("El archivo no contiene stream de video válido")
            
    except subprocess.TimeoutExpired:
        raise CorruptedFileError("Timeout al validar el archivo de video")
    except subprocess.CalledProcessError:
        raise CorruptedFileError("El archivo no es un video válido o está corrupto")

def get_quality_settings(quality_preset):
    """Obtiene los ajustes de calidad según el preset seleccionado"""
    quality_presets = {
        "alta_calidad": {"crf": "18", "preset": "slow", "audio_bitrate": "192k"},
        "balanceado": {"crf": "23", "preset": "medium", "audio_bitrate": "128k"},
        "compresion": {"crf": "28", "preset": "fast", "audio_bitrate": "96k"},
        "extrema": {"crf": "32", "preset": "veryfast", "audio_bitrate": "64k"}
    }
    
    return quality_presets.get(quality_preset, quality_presets["balanceado"])

def parse_duration(duration_str):
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

def parse_progress(line, total_duration):
    """Parsea el progreso de la salida de ffmpeg"""
    match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
    if match and total_duration > 0:
        current_time = parse_duration(match.group(1))
        progress = int((current_time / total_duration) * 100)
        return min(progress, 100)
    return None

def check_disk_space(output_file, required_bytes):
    """Verifica que haya espacio suficiente en disco"""
    output_path = Path(output_file)
    if output_path.exists():
        required_bytes -= output_path.stat().st_size
        
    try:
        disk_usage = os.path.splitdrive(output_file)[0] + os.path.sep
        free_space = os.path.getfree(disk_usage)
        if free_space < required_bytes * 1.1:  # 10% de margen
            raise ConversionError(f"Espacio en disco insuficiente. Se requieren {required_bytes // (1024*1024)}MB")
    except Exception:
        # Si no se puede verificar el espacio, continuar con advertencia
        pass

def get_ffmpeg_command(input_file, output_file, mode, quality_preset="balanceado"):
    """Construye el comando ffmpeg con las rutas escapadas correctamente"""
    
    if mode == 'convert':
        # SOLO CONVERSIÓN - SIN COMPRIMIR (copy codecs)
        return [
            "ffmpeg", "-i", shlex.quote(input_file),
            "-c:v", "copy", "-c:a", "copy",  # Copiar sin re-codificar
            shlex.quote(output_file), "-y"
        ]
    
    # MODO COMPRESIÓN - usar ajustes de calidad
    quality_settings = get_quality_settings(quality_preset)
    
    codec_configs = {
        '.mp4': {"vcodec": "libx264", "acodec": "aac"},
        '.webm': {"vcodec": "libvpx-vp9", "acodec": "libopus"},
        '.mov': {"vcodec": "libx264", "acodec": "aac"},
        '.mkv': {"vcodec": "libx264", "acodec": "aac"},
        '.avi': {"vcodec": "mpeg4", "qscale": "5", "acodec": "mp3"}
    }
    
    output_ext = Path(output_file).suffix.lower()
    config = codec_configs.get(output_ext, codec_configs['.mp4'])
    
    cmd = ["ffmpeg", "-i", shlex.quote(input_file)]
    
    if 'qscale' in config:
        cmd.extend(["-c:v", config["vcodec"], "-qscale:v", config["qscale"]])
    else:
        cmd.extend(["-c:v", config["vcodec"], "-crf", quality_settings["crf"]])
        if quality_settings["preset"]:
            cmd.extend(["-preset", quality_settings["preset"]])
    
    cmd.extend([
        "-c:a", config["acodec"], "-b:a", quality_settings["audio_bitrate"],
        shlex.quote(output_file), "-y"
    ])
    
    return cmd

def get_video_duration(input_file):
    """Obtiene la duración total del video"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            capture_output=True, text=True, check=True, timeout=30
        )
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, subprocess.CalledProcessError):
        return 0