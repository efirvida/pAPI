import logging
import sys
from pathlib import Path

from loguru import logger
from loguru._defaults import LOGURU_FORMAT

from papi.core.models.config import LoggerLevel
from papi.core.settings import get_config


class InterceptHandler(logging.Handler):
    """
    Intercepts standard logging and forwards it to Loguru with proper context.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(logger_name=record.name).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


def setup_logging() -> None:
    """
    Configures logging for both stdlib and Loguru.
    """
    try:
        config = get_config()
    except Exception as e:
        logger.warning(f"configure logger 2 {e}")
    if not config.logger.level:
        level = LoggerLevel.INFO
    else:
        level = config.logger.level.upper()

    LOG_LEVEL = logging.getLevelName(level)
    JSON_LOGS = config.logger.json_log
    LOG_FILE = config.logger.log_file

    # Remove handlers from root logger and set level
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(LOG_LEVEL)

    # Remove all other loggers' handlers and propagate to root
    for name in logging.root.manager.loggerDict.keys():
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True

    # Build loguru handler configuration
    handlers = []

    # Console output
    handlers.append({
        "sink": sys.stdout,
        "level": LOG_LEVEL,
        "serialize": JSON_LOGS,
        "backtrace": True,
        "diagnose": LOG_LEVEL == "DEBUG",
        "format": LOGURU_FORMAT,
    })

    # Optional file output
    if LOG_FILE:
        log_file = Path(LOG_FILE)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        handlers.append({
            "sink": str(log_file),
            "level": LOG_LEVEL,
            "serialize": JSON_LOGS,
            "rotation": "100 MB",
            "retention": "30 days",
            "compression": "zip",
            "encoding": "utf-8",
            "backtrace": False,
            "diagnose": False,
            "format": (
                None
                if JSON_LOGS
                else "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[logger_name]}:{function}:{line} - {message}"
            ),
        })
    logger.configure(
        handlers=handlers,
        extra={"logger_name": "pAPI"},
    )
    logger.info("Logging initialized.")
