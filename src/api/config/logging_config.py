"""
Centralized logging configuration for BIMFabrikHH API.

Provides :func:`setup_logging`, an idempotent helper that configures the root
logger with two handlers:

* a console (stream) handler, and
* a multiprocess-safe, time-rotating file handler writing to a single shared
  log file (safe across the FastAPI process and the Celery worker subprocess,
  including Celery ``prefork`` child processes).

Both handlers have independently configurable log levels, and all values are
sourced from the application settings (which load from ``.env``).

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging
import logging.config
from pathlib import Path

from .settings import PROJECT_ROOT, api_settings

# Log record format shared by both handlers.
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Guard so repeated calls within a single process do not rebuild the config.
_configured = False


def _resolve_log_file_path() -> Path:
    """Return the absolute log file path, resolving relative paths.

    Relative ``LOG_FILE_PATH`` values are resolved against the project root so
    behaviour is independent of the current working directory.
    """
    configured = Path(api_settings.LOG_FILE_PATH)
    if not configured.is_absolute():
        configured = PROJECT_ROOT / configured
    return configured


def setup_logging(force: bool = False) -> None:
    """Configure application-wide logging.

    Sets up the root logger with a console handler and, when enabled, a
    multiprocess-safe time-rotating file handler. The function is idempotent:
    subsequent calls within the same process are ignored unless ``force`` is
    ``True``.

    Args:
        force: Rebuild the configuration even if logging was already set up in
            this process.
    """
    global _configured
    if _configured and not force:
        return

    console_level = api_settings.LOG_LEVEL_CONSOLE.upper()
    file_level = api_settings.LOG_LEVEL_FILE.upper()

    handlers: dict[str, dict] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": console_level,
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        }
    }

    # Root must be at least as verbose as the most verbose handler, otherwise
    # records are filtered out before reaching the handlers.
    active_levels = [console_level]

    log_file: Path | None = None
    if api_settings.LOG_FILE_ENABLED:
        log_file = _resolve_log_file_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)

        handlers["file"] = {
            "class": "concurrent_log_handler.ConcurrentTimedRotatingFileHandler",
            "level": file_level,
            "formatter": "standard",
            "filename": str(log_file),
            "when": api_settings.LOG_FILE_WHEN,
            "backupCount": api_settings.LOG_FILE_BACKUP_COUNT,
            "encoding": "utf-8",
        }
        active_levels.append(file_level)

    root_level = min(
        (logging.getLevelName(lvl) for lvl in active_levels),
        default=logging.INFO,
    )

    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": LOG_FORMAT,
                "datefmt": LOG_DATE_FORMAT,
            }
        },
        "handlers": handlers,
        "root": {
            "level": root_level,
            "handlers": list(handlers.keys()),
        },
        # Route uvicorn's own loggers through the root handlers so that access
        # and error logs share the same format and destinations.
        "loggers": {
            "uvicorn": {"handlers": [], "level": root_level, "propagate": True},
            "uvicorn.error": {"handlers": [], "level": root_level, "propagate": True},
            "uvicorn.access": {"handlers": [], "level": root_level, "propagate": True},
        },
    }

    try:
        logging.config.dictConfig(config)
    except (ValueError, OSError) as exc:
        # A logging/file problem (e.g. the log file is not writable) must never
        # prevent the application from starting. Fall back to console-only
        # logging and continue, emitting a warning through the console handler.
        if "file" not in handlers:
            raise
        del handlers["file"]
        config["root"]["handlers"] = list(handlers.keys())
        logging.config.dictConfig(config)
        logging.getLogger(__name__).warning(
            "Could not configure file log handler for %s (%s); "
            "falling back to console logging only.",
            log_file,
            exc,
        )

    _configured = True
