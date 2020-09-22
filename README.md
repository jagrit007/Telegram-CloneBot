# Why?
For all my friends using my TDs who now need to store everything in it instead of their Drive. [Need help?](https://t.me/tgclonebot)

<p align="center">
<img src="https://i.imgur.com/CXy0SPB.jpg" alt="drawing" width="270" height=585/>
</p>

## Guide:
- YouTube Guide: [Google Drive Clone Bot Set-Up Tutorial | Telegram Bot Setup Guide](https://www.youtube.com/watch?v=2r3_jR7SvUo&feature=youtu.be)
  - Follow the above guide for Heroku.
  - If you wish to run on a VPS, Do all the stuff I did on the VPS Terminal ;)
  - Wish to run anywhere else? Follow the guide till the part where I download ZIP Archive from Repl.it. Use that zip on any device you'd like to run the bot on. 
  - Don't forget to install requirements.txt
    ```
    pip3 install -r requirements.txt
    ```
- [Adding Service Accounts to Google Group/TeamDrive](https://youtu.be/pBfsmJhYr78)

## Setting up config file (present in bot/config.py)
- **BOT_TOKEN** : The telegram bot token that you get from @BotFather
- **GDRIVE_FOLDER_ID** : This is the folder ID of the Google Drive Folder to which you want to clone.
- **OWNER_ID** : The Telegram user ID (not username) of the owner of the bot (if you do not have that, send /id to @kelverbot )
- **AUTHORISED_USERS** : The Telegram user IDs (not username) of people you wish to allow for bot access.It can also be group chat id. Write like: [123456, 4030394, -1003823820]
- **IS_TEAM_DRIVE** : (Optional field) Set to True if GDRIVE_FOLDER_ID is from a Team Drive else False or Leave it empty.
- **USE_SERVICE_ACCOUNTS**: (Optional field) (Leave empty if unsure) Whether to use service accounts or not. For this to work see  "Using service accounts" section below.
- **INDEX_URL** : (Optional field) Refer to https://github.com/maple3142/GDIndex/ The URL should not have any trailing '/'

## Getting Google OAuth API credential file

- Visit the [Google Cloud Console](https://console.developers.google.com/apis/credentials)
- Go to the OAuth Consent tab, fill it, and save.
- Go to the Credentials tab and click Create Credentials -> OAuth Client ID
- Choose Other and Create.
- Use the download button to download your credentials.
- Move that file to the root of clone-bot, and rename it to credentials.json
- Visit [Google API page](https://console.developers.google.com/apis/library)
- Search for Drive and enable it if it is disabled
- Finally, run the script to generate token file (token.pickle) for Google Drive:
```
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
python3 generate_drive_token.py
```
# Running
- To run this bot (locally) (suggested)
```
python3 -m bot
```
- Deploying to Heroku (Optional) (Not Suitable for very big Clones!)

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?template=https://github.com/jagrit007/Telegram-CloneBot)

- Please know that after using this button, your work isn't done. You gotta [clone heroku app](https://devcenter.heroku.com/articles/git-clone-heroku-app) and add credentials.json and token.pickle (By now you would know how to make it.) and this is the perfect time to generate service accounts if you wish to use them. After it's all done, [Push changes to Heroku (Step1-2 only).](https://docs.railsbridge.org/intro-to-rails/deploying_to_heroku_again)

**Tip: Instead of using Termux or local machine, use [repl.it](https://repl.it/), atleast it won't throw any errors in installing Python requirements. From [repl.it](https://repl.it/) you could push to a private GitHub repo and attach that to Heroku.**


# Using service accounts for uploading to avoid user rate limit
For Service Account to work, you must set USE_SERVICE_ACCOUNTS=True in config file or environment variables
Many thanks to [AutoRClone](https://github.com/xyou365/AutoRclone) for the scripts
## Generating service accounts
Step 1. Generate service accounts [What is service account](https://cloud.google.com/iam/docs/service-accounts)
---------------------------------
Let us create only the service accounts that we need. 
**Warning:** abuse of this feature is not the aim of autorclone and we do **NOT** recommend that you make a lot of projects, just one project and 100 sa allow you plenty of use, its also possible that overabuse might get your projects banned by google. 

```
Note: 1 service account can copy around 750gb a day, 1 project makes 100 service accounts so thats 75tb a day, for most users this should easily suffice. 
```

`python3 gen_sa_accounts.py --quick-setup 1 --new-only`

A folder named accounts will be created which will contain keys for the service accounts created

NOTE: If you have created SAs in past from this script, you can also just re download the keys by running:
```
python3 gen_sa_accounts.py --download-keys project_id
```

### Add all the service accounts to the Team Drive or folder
- Run:
```
python3 add_to_team_drive.py -d SharedTeamDriveSrcID
```

### Credits
- https://github.com/jagrit007
- https://github.com/lzzy12/python-aria-mirror-bot
- https://github.com/xyou365/AutoRclone
