from functools import wraps
from bot.config import OWNER_ID, AUTHORISED_USERS

def is_authorised(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if args[0].effective_message.from_user.id in AUTHORISED_USERS or args[0].message.chat_id in AUTHORISED_USERS:
            return func(*args, **kwargs)
        elif args[0].effective_message.from_user.id == OWNER_ID:
            return func(*args, **kwargs)
        else:
            return False
    return wrapper

def is_owner(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if args[0].effective_message.from_user.id == OWNER_ID:
            return func(*args, **kwargs)
        else:
            return False
    return wrapper
