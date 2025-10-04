import re
from pathlib import Path

def is_filename_problematic(file_path: str, max_length: int = 100) -> bool:
    """
    Devuelve True si el nombre de archivo podría causar problemas en FFmpeg en Linux.
    Detecta nombres muy largos o caracteres especiales/emoji.
    """
    p = Path(file_path)
    name = p.name

    # Nombre demasiado largo
    if len(name) > max_length:
        return True

    # Contiene caracteres no ASCII (emoji, símbolos raros)
    if not all(ord(c) < 128 for c in name):
        return True

    return False
