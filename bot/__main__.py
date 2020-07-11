from telegram.message import Message
from telegram.update import Update
from telegram.ext import CommandHandler, run_async
from bot.gDrive import GoogleDriveHelper
from bot import LOGGER, dispatcher, updater, bot
from bot.config import BOT_TOKEN
from telegram.error import TimedOut, BadRequest


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


@run_async
def start(update, context):
    sendMessage("Alive!", context.bot, update)
    # ;-;


@run_async
def cloneNode(update,context):
    args = update.message.text.split(" ",maxsplit=1)
    if len(args) > 1:
        link = args[1]
        msg = sendMessage(f"Cloning: <code>{link}</code>",context.bot,update)
        gd = GoogleDriveHelper()
        result = gd.clone(link)
        deleteMessage(context.bot,msg)
        sendMessage(result,context.bot,update)
    else:
        sendMessage("Please Provide a Google Drive Shared Link to Clone.", bot, update)


def main():
    clone_handler = CommandHandler('clone', cloneNode)
    dispatcher.add_handler(clone_handler)
    updater.start_polling()

main()