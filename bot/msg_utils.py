from bot import LOGGER
from telegram.message import Message
from telegram.update import Update

def deleteMessage(bot, message: Message):
    try:
        bot.delete_message(chat_id=message.chat.id,
                           message_id=message.message_id)
    except Exception as e:
        LOGGER.error(str(e))


def sendMessage(text: str, bot, update: Update, parse_mode='HTMl'):
    return bot.send_message(update.message.chat_id,
                            reply_to_message_id=update.message.message_id,
                            text=text, parse_mode=parse_mode)


#To-do: One clone message for all clones; clone cancel command 