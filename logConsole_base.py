# recycled logger from previous code/scripts
import logging
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback

console = Console()

_logging_initialized = False


# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_logging(
    debug: bool = True,
    enable_file: bool = True,
    log_dir: str | Path = "logs",
    prefix: str = "log_"
) -> Path | None:

    global _logging_initialized

    if _logging_initialized:
        return None

    install_rich_traceback(show_locals=False)

    log_dir = Path(log_dir)

    level = logging.DEBUG if debug else logging.INFO

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    # Console handler (Rich)
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        omit_repeated_times=False,
        show_path=False,
        markup=True,
        rich_tracebacks=True
    )

    console_handler.setFormatter(
        logging.Formatter("%(message)s")
    )

    root_logger.addHandler(console_handler)

    logfile = None

    # File handler
    if enable_file:

        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logfile = log_dir / f"{prefix}{timestamp}.log"

        file_handler = logging.FileHandler(
            logfile,
            encoding="utf-8"
        )

        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        #logging.debug(f"Log file created: {logfile}")

    _logging_initialized = True

    return logfile


# =============================================================================
# LOGGER ACCESS
# =============================================================================

def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name)
