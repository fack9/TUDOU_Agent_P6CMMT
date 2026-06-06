import logging
import sys
from pathlib import Path

def setup_logging(level: str='INFO', log_file: Path | None=None) -> logging.Logger:
    logger = logging.getLogger('tudou_agent')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(handler)
        if log_file:
            fh = logging.FileHandler(str(log_file), encoding='utf-8')
            fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            logger.addHandler(fh)
    return logger
TUDOU_log = setup_logging()
