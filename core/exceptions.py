# --- Excepciones personalizadas ---
class FFmpegNotFoundError(Exception):
    pass

class CorruptedFileError(Exception):
    pass

class ConversionError(Exception):
    pass