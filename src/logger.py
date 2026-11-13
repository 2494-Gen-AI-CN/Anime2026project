import logging
from pathlib import Path

DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "pipeline.log"


class PipelineLogger:

    _instance: logging.Logger | None = None

    @classmethod
    def get_logger(cls, log_file: Path | str = DEFAULT_LOG_FILE, level: int = logging.INFO) -> logging.Logger:
        if cls._instance is not None:
            return cls._instance

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger("anime_dw")
        logger.setLevel(level)
        logger.propagate = False

        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            console = logging.StreamHandler()
            console.setFormatter(formatter)

            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)

            logger.addHandler(console)
            logger.addHandler(file_handler)

        cls._instance = logger
        return cls._instance
