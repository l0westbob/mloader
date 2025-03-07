import logging
import sys


def setup_logging():
    """
    Configure logging for the application.

    Sets third-party loggers (e.g., 'requests', 'urllib3') to WARNING and configures the
    root logger to output logs to stdout with a custom format.
    """
    for logger_name in ("requests", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    stream_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        handlers=[stream_handler],
        format=(
            "{asctime:^} | {levelname: ^8} | {filename: ^14} {lineno: <4} | {message}"
        ),
        style="{",
        datefmt="%d.%m.%Y %H:%M:%S",
        level=logging.INFO,
    )


# Immediately configure logging upon module import.
setup_logging()


def get_logger(name: str = None) -> logging.Logger:
    """
    Retrieve a logger instance with the given name.

    Parameters:
        name (str, optional): The name of the logger. Defaults to None for the root logger.

    Returns:
        logging.Logger: The configured logger.
    """
    return logging.getLogger(name)