# app/utils/logger.py
"""Logger centralizado para el proyecto.

Provee un logger configurado por nivel y con handlers para consola y archivo.
Uso:
	from app.utils.logger import get_logger
	log = get_logger(__name__)
	log.info("Mensaje")

Se integra con `settings.LOG_FILE` y `settings.LOG_LEVEL` si existen.
"""
import logging
import logging.handlers
import os
from typing import Optional

def configure_process_stdio_utf8() -> None:
    """Prevent Windows charmap/cp1252 failures for emoji and accents."""
    for stream in (getattr(__import__("sys"), "stdout", None), getattr(__import__("sys"), "stderr", None)):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


configure_process_stdio_utf8()

try:
	from app.config import settings
except Exception:
	settings = None


_MOJIBAKE_MARKERS = ("├", "┬", "Â", "Ã", "Ô", "â", "ð", "�")

def _repair_mojibake(text: str) -> str:
    """Repair common UTF-8-as-Windows-1252 text without touching normal text."""
    if not isinstance(text, str) or not any(m in text for m in _MOJIBAKE_MARKERS):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
        return repaired if repaired else text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

class _UTF8Formatter(logging.Formatter):
    def format(self, record):
        return _repair_mojibake(super().format(record))


def _ensure_log_dir(path: str) -> None:
	d = os.path.dirname(path)
	if d and not os.path.exists(d):
		try:
			os.makedirs(d, exist_ok=True)
		except Exception:
			pass


def get_logger(name: str, *, log_file: Optional[str] = None, level: Optional[str] = None) -> logging.Logger:
	logger = logging.getLogger(name)
	if logger.handlers:
		return logger

	lvl_name = level or (getattr(settings, "LOG_LEVEL", "INFO") if settings else "INFO")
	lvl = getattr(logging, lvl_name.upper(), logging.INFO)
	logger.setLevel(lvl)

	log_format = getattr(settings, "LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s") if settings else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
	max_bytes = getattr(settings, "LOG_MAX_BYTES", 10 * 1024 * 1024) if settings else 10 * 1024 * 1024
	backup_count = getattr(settings, "LOG_BACKUP_COUNT", 5) if settings else 5


	import sys
	ch = logging.StreamHandler(sys.stdout)
	ch.setLevel(lvl)
	ch_formatter = _UTF8Formatter(log_format)
	ch.setFormatter(ch_formatter)
	logger.addHandler(ch)


	logfile = log_file or (getattr(settings, "LOG_FILE", None) if settings else None)
	if logfile:
		try:
			_ensure_log_dir(logfile)
			fh = logging.handlers.RotatingFileHandler(logfile, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
			fh.setLevel(lvl)
			fh_formatter = _UTF8Formatter(log_format)
			fh.setFormatter(fh_formatter)
			logger.addHandler(fh)
		except Exception:
			pass


	logger.propagate = False
	return logger



root = get_logger("bot")
