import logging
from logging import handlers
from pathlib import Path

from pzsd_bot import settings

logger = logging.getLogger()
logger.setLevel(logging.DEBUG if settings.DEBUG_MODE else logging.INFO)
log_file = Path(__file__).parents[1] / Path("logs", "pzsd_bot.log")
log_file.parent.mkdir(exist_ok=True)
handler = handlers.RotatingFileHandler(
    log_file, maxBytes=3 * 1024**2, backupCount=2, encoding="utf8"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(stream_handler)
