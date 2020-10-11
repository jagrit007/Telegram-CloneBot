import os
import pickle
import urllib.parse as urlparse
from urllib.parse import parse_qs
from bot import LOGGER

import json
import logging
import re
import requests
import socket

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import *

from bot.config import IS_TEAM_DRIVE, \
            USE_SERVICE_ACCOUNTS, GDRIVE_FOLDER_ID, INDEX_URL
from bot.fs_utils import get_mime_type

logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
socket.setdefaulttimeout(650) # https://github.com/googleapis/google-api-python-client/issues/632#issuecomment-541973021
SERVICE_ACCOUNT_INDEX = 0

def clean_name(name):
    name = name.replace("'", "\\'")
    return name

class GoogleDriveHelper:
    def __init__(self, name=None, listener=None, GFolder_ID=GDRIVE_FOLDER_ID):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        # Redirect URI for installed apps, can be left as is
        self.__REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__G_DRIVE_BASE_DOWNLOAD_URL = "https://drive.google.com/uc?id={}&export=download"
        self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL = "https://drive.google.com/drive/folders/{}"
        self.__listener = listener
        self.__service = self.authorize()
        self.__listener = listener
        self._file_uploaded_bytes = 0
        self.uploaded_bytes = 0
        self.UPDATE_INTERVAL = 5
        self.start_time = 0
        self.total_time = 0
        self._should_update = True
        self.is_uploading = True
        self.is_cancelled = False
        self.status = None
        self.updater = None
        self.name = name
        self.update_interval = 3
        if not len(GFolder_ID) == 33 or not len(GFolder_ID) == 19:
            self.gparentid = self.getIdFromUrl(GFolder_ID)
        else:
            self.gparentid = GFolder_ID

    def cancel(self):
        self.is_cancelled = True
        self.is_uploading = False

    def speed(self):
        """
        It calculates the average upload speed and returns it in bytes/seconds unit
        :return: Upload speed in bytes/second
        """
        try:
            return self.uploaded_bytes / self.total_time
        except ZeroDivisionError:
            return 0

    @staticmethod
    def getIdFromUrl(link: str):
        if len(link) in [33, 19]:
            return link
        if "folders" in link or "file" in link:
            regex = r"https://drive\.google\.com/(drive)?/?u?/?\d?/?(mobile)?/?(file)?(folders)?/?d?/(?P<id>[-\w]+)[?+]?/?(w+)?"
            res = re.search(regex,link)
            if res is None:
                raise IndexError("GDrive ID not found.")
            return res.group('id')
        parsed = urlparse.urlparse(link)
        return parse_qs(parsed.query)['id'][0]

    def switchServiceAccount(self):
        global SERVICE_ACCOUNT_INDEX
        service_account_count = len(os.listdir("accounts"))
        if SERVICE_ACCOUNT_INDEX == service_account_count - 1:
            SERVICE_ACCOUNT_INDEX = 0
        SERVICE_ACCOUNT_INDEX += 1
        LOGGER.info(f"Switching to {SERVICE_ACCOUNT_INDEX}.json service account")
        self.__service = self.authorize()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def __set_permission(self, drive_id):
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        return self.__service.permissions().create(supportsTeamDrives=True, fileId=drive_id,
                                                   body=permissions).execute()


    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def copyFile(self, file_id, dest_id, status):
        body = {
            'parents': [dest_id]
        }

        try:
            res = self.__service.files().copy(supportsAllDrives=True,fileId=file_id,body=body).execute()
            return res
        except HttpError as err:
            if err.resp.get('content-type', '').startswith('application/json'):
                reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
                if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
                    if USE_SERVICE_ACCOUNTS:
                        self.switchServiceAccount()
                        LOGGER.info(f"Got: {reason}, Trying Again.")
                        self.copyFile(file_id, dest_id, status)
                else:
                    raise err

    def clone(self, link, status, ignoreList=[]):
        self.transferred_size = 0
        try:
            file_id = self.getIdFromUrl(link)
        except (KeyError,IndexError):
            msg = "Google drive ID could not be found in the provided link"
            return msg
        msg = ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.__service.files().get(supportsAllDrives=True, fileId=file_id,
                                              fields="name,id,mimeType,size").execute()
            dest_meta = self.__service.files().get(supportsAllDrives=True, fileId=self.gparentid,
                                              fields="name,id,size").execute()
            status.SetMainFolder(meta.get('name'), self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(meta.get('id')))
            status.SetDestinationFolder(dest_meta.get('name'), self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dest_meta.get('id')))
        except Exception as e:
            return f"{str(e).replace('>', '').replace('<', '')}"
        if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE:
            dir_id = self.check_folder_exists(meta.get('name'), self.gparentid)
            if not dir_id:
                dir_id = self.create_directory(meta.get('name'), self.gparentid)
            try:
                self.cloneFolder(meta.get('name'), meta.get('name'), meta.get('id'), dir_id, status, ignoreList)
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = str(e).replace('>', '').replace('<', '')
                LOGGER.error(err)
                return err
            status.set_status(True)
            msg += f'<a href="{self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)}">{meta.get("name")}</a>' \
                   f' ({get_readable_file_size(self.transferred_size)})'
            if INDEX_URL:
                url = requests.utils.requote_uri(f'{INDEX_URL}/{meta.get("name")}/')
                msg += f' | <a href="{url}"> Index URL</a>'
        else:
            try:
                file = self.check_file_exists(meta.get('id'), self.gparentid)
                if file:
                    status.checkFileExist(True)
                if not file:
                    status.checkFileExist(False)
                    file = self.copyFile(meta.get('id'), self.gparentid, status)
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = str(e).replace('>', '').replace('<', '')
                LOGGER.error(err)
                return err
            msg += f'<a href="{self.__G_DRIVE_BASE_DOWNLOAD_URL.format(file.get("id"))}">{file.get("name")}</a>'
            try:
                msg += f' ({get_readable_file_size(int(meta.get("size")))}) '
                if INDEX_URL is not None:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}')
                    msg += f' | <a href="{url}"> Index URL</a>'
            except TypeError:
                pass
        return msg

    def cloneFolder(self, name, local_path, folder_id, parent_id, status, ignoreList=[]):
        page_token = None
        q = f"'{folder_id}' in parents"
        files = []
        LOGGER.info(f"Syncing: {local_path}")
        while True:
            response = self.__service.files().list(supportsTeamDrives=True,
                                                   includeTeamDriveItems=True,
                                                   q=q,
                                                   spaces='drive',
                                                   fields='nextPageToken, files(id, name, mimeType,size)',
                                                   pageToken=page_token).execute()
            for file in response.get('files', []):
                files.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        if len(files) == 0:
            return parent_id
        for file in files:
            if file.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                file_path = os.path.join(local_path, file.get('name'))
                current_dir_id = self.check_folder_exists(file.get('name'), parent_id)
                if not current_dir_id:
                    current_dir_id = self.create_directory(file.get('name'), parent_id)
                if not str(file.get('id')) in ignoreList:
                    self.cloneFolder(file.get('name'), file_path, file.get('id'), current_dir_id, status, ignoreList)
                else:
                    LOGGER.info("Ignoring FolderID from clone: " + str(file.get('id')))
            else:
                try:
                    if not self.check_file_exists(file.get('name'), parent_id):
                        status.checkFileExist(False)
                        self.copyFile(file.get('id'), parent_id, status)
                        self.transferred_size += int(file.get('size'))
                        status.set_name(file.get('name'))
                        status.add_size(int(file.get('size')))
                    else:
                        status.checkFileExist(True)
                except TypeError:
                    pass
                except Exception as e:
                    if isinstance(e, RetryError):
                        LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                        err = e.last_attempt.exception()
                    else:
                        err = e
                    LOGGER.error(err)

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def create_directory(self, directory_name, parent_id):
        file_metadata = {
            "name": directory_name,
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        file = self.__service.files().create(supportsTeamDrives=True, body=file_metadata).execute()
        file_id = file.get("id")
        if not IS_TEAM_DRIVE:
            self.__set_permission(file_id)
        LOGGER.info("Created Google-Drive Folder:\nName: {}\nID: {} ".format(file.get("name"), file_id))
        return file_id


    def authorize(self):
        # Get credentials
        credentials = None
        if not USE_SERVICE_ACCOUNTS:
            if os.path.exists(self.__G_DRIVE_TOKEN_FILE):
                with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                    credentials = pickle.load(f)
            if credentials is None or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.__OAUTH_SCOPE)
                    LOGGER.info(flow)
                    credentials = flow.run_console(port=0)

                # Save the credentials for the next run
                with open(self.__G_DRIVE_TOKEN_FILE, 'wb') as token:
                    pickle.dump(credentials, token)
        else:
            LOGGER.info(f"Authorizing with {SERVICE_ACCOUNT_INDEX}.json service account")
            credentials = service_account.Credentials.from_service_account_file(
                f'accounts/{SERVICE_ACCOUNT_INDEX}.json',
                scopes=self.__OAUTH_SCOPE)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def check_folder_exists(self, fileName, u_parent_id):
        fileName = clean_name(fileName)
        # Create Search Query for API request.
        query = f"'{u_parent_id}' in parents and (name contains '{fileName}' and trashed=false)"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=5,
                                               fields='files(id, name, mimeType, size)',
                                               orderBy='modifiedTime desc').execute()
        for file in response.get('files', []):
            if file.get('mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                    driveid = file.get('id')
                    return driveid
    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def check_file_exists(self, fileName, u_parent_id):
        fileName = clean_name(fileName)
        # Create Search Query for API request.
        query = f"'{u_parent_id}' in parents and (name contains '{fileName}' and trashed=false)"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=5,
                                               fields='files(id, name, mimeType, size)',
                                               orderBy='modifiedTime desc').execute()
        for file in response.get('files', []):
            if file.get('mimeType') != "application/vnd.google-apps.folder":
                    # driveid = file.get('id')
                    return file


def get_readable_file_size(size_in_bytes) -> str:
    SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'

