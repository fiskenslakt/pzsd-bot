import logging
from logging import handlers
from pathlib import Path

from pzsd_bot.settings import Bot

logger = logging.getLogger()
logger.setLevel(Bot.log_level)
log_file = Path(__file__).parents[1] / Path("logs", "pzsd_bot.log")
log_file.parent.mkdir(exist_ok=True)
handler = handlers.RotatingFileHandler(
    log_file, maxBytes=3 * 1024**2, backupCount=2, encoding="utf8"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)
