import logging
from typing import ClassVar


class ColorFormatter(logging.Formatter):
    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[1;91m",  # Bright bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord):
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.RESET)
        record.levelname = f"{color}{levelname}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter("[%(asctime)s] %(levelname)s - %(message)s", datefmt="%H:%M:%S"))

logger = logging.getLogger("tts")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

logging.getLogger("httpx").setLevel(logging.WARNING)
