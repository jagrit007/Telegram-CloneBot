import logging
import time
import os
import telegram.ext as tg
from bot.config import BOT_TOKEN

if os.path.exists('log.txt'):
    with open('log.txt', 'r+') as f:
        f.truncate(0)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
                    level=logging.INFO)

LOGGER = logging.getLogger(__name__)
updater = tg.Updater(token=BOT_TOKEN, use_context=True, workers=16)
bot = updater.bot
dispatcher = updater.dispatcher