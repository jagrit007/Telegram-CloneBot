import os
from distutils.util import strtobool as stb

# --------------------------------------
BOT_TOKEN = ""
GDRIVE_FOLDER_ID = ""
OWNER_ID = 123455673
# Example: OWNER_ID = 619418070
INDEX_URL = ""
IS_TEAM_DRIVE = True
USE_SERVICE_ACCOUNTS = True
# --------------------------------------

# dont edit below this >



BOT_TOKEN = os.environ.get('BOT_TOKEN', BOT_TOKEN)
GDRIVE_FOLDER_ID = os.environ.get('GDRIVE_FOLDER_ID', GDRIVE_FOLDER_ID)
OWNER_ID = int(os.environ.get('OWNER_ID', OWNER_ID))
INDEX_URL = os.environ.get('INDEX_URL', INDEX_URL)
IS_TEAM_DRIVE = stb(os.environ.get('IS_TEAM_DRIVE', IS_TEAM_DRIVE))
USE_SERVICE_ACCOUNTS = stb(os.environ.get('USE_SERVICE_ACCOUNTS', USE_SERVICE_ACCOUNTS))
