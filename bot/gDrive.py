import os
import re
import glob
import pickle
import urllib.parse as urlparse
from urllib.parse import parse_qs
from bot import LOGGER

import json
import random
import time
import threading
import logging
import requests
import socket

from socket import timeout
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ssl import SSLError
from googleapiclient.http import MediaFileUpload
from tenacity import *

from bot.config import IS_TEAM_DRIVE, \
            USE_SERVICE_ACCOUNTS, GDRIVE_FOLDER_ID, INDEX_URL, THREAD_COUNT
from bot.fs_utils import get_mime_type

logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
socket.setdefaulttimeout(650) # https://github.com/googleapis/google-api-python-client/issues/632#issuecomment-541973021

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

        self.usedServiceAccountsList = []
        self.accountsList = glob.glob(os.path.join('accounts', '*.json'))
        self.__service = self.authorize()
        self.cancelled = False

        self.name = name
        self.threads = threading.BoundedSemaphore(THREAD_COUNT)
        
        # self.FileCopythreads = threading.BoundedSemaphore(2) # leave this as it is for now, only decrease it if you wish.
        self.threadsList = list()
        # self.CopyThreadList = []

        if not len(GFolder_ID) in [33, 19]:
            self.gparentid = self.getIdFromUrl(GFolder_ID)
        else:
            self.gparentid = GFolder_ID


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


    def authorize(self, sa_json=None):
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
            if not sa_json:
                sa_json = self.pickRandomUnusedJSON()
            credentials = service_account.Credentials.from_service_account_file(
                filename=sa_json,
                scopes=self.__OAUTH_SCOPE)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)
    

    def switchServiceAccount(self):
        JSONfile = self.pickRandomUnusedJSON()        

        self.__service = self.authorize(JSONfile)
        LOGGER.info(f'Using {os.path.basename(JSONfile)} Service Account')
        return self.__service

    
    def pickRandomUnusedJSON(self):
        JSONfile = random.choice(self.accountsList)
        if len(self.usedServiceAccountsList) == len(self.accountsList):
            self.usedServiceAccountsList = []
            JSONfile = self.pickRandomUnusedJSON()
        
        if JSONfile not in self.usedServiceAccountsList:
            self.usedServiceAccountsList.append(JSONfile)
            # return JSONfile
        else:
            JSONfile = self.pickRandomUnusedJSON()

        return JSONfile
    
    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def __set_permission(self, drive_id):
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        return self.__service.permissions().create(supportsAllDrives=True, fileId=drive_id,
                                                   body=permissions).execute()


    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError) | retry_if_exception_type(AttributeError) | retry_if_exception_type(OSError), before=before_log(LOGGER, logging.DEBUG))
    def copyFile(self, file_id, dest_id, status, service_object=None):
        # self.__service = self.authorize()
        if self.cancelled:
            return
        if not service_object:
            service_object = self.__service
        body = {
            'parents': [dest_id]
        }

        try:
            res = service_object.files().copy(supportsAllDrives=True, fileId=file_id, body=body).execute()
            return res
        except HttpError as err:
            if err.resp.get('content-type', '').startswith('application/json'):
                reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
                if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
                    if USE_SERVICE_ACCOUNTS:
                        service_object = self.switchServiceAccount()
                        LOGGER.info(f"Got: {reason}, Trying Again.")
                        self.copyFile(file_id, dest_id, status, service_object)
                else:
                    raise err
            else:
                raise err
        except Exception as e:
            try:
                self.threads.release()
            except:
                pass
            LOGGER.error(e)
            raise e

    # @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
    #        retry=retry_if_exception_type(HttpError) | retry_if_exception_type(SSLError) | retry_if_exception_type(AttributeError) | retry_if_exception_type(OSError), before=before_log(LOGGER, logging.DEBUG))
    # def ThreadedCopyFiles(self, file_list, source_id, destination_id, status_object, service_object=None):
    #     # service_Temp = self.authorize()
    #     if not service_object:
    #         service_object = self.authorize()
    #     # destination_list = self.listFolderFiles(destination_id, service_object)
    #     for file in file_list:
    #         file_exists = self.check_file_exists(file, destination_id, service_object)
    #         if not file_exists:
    #             try:
    #                 status_object.checkFileExist(False)
    #                 body = {'parents': [destination_id]}
    #                 self.transferred_size += int(file.get('size'))
    #                 status_object.set_name(file.get('name'))
    #                 status_object.add_size(int(file.get('size')))
    #                 service_object.files().copy(supportsAllDrives=True, fileId=file.get('id'), body=body).execute()
    #                 LOGGER.info(f"Cloned file: {file.get('name')}")
    #                 # file_list.remove(file)
    #             except HttpError as err:
    #                 if err.resp.get('content-type', '').startswith('application/json'):
    #                     reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
    #                 if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
    #                     if USE_SERVICE_ACCOUNTS:
    #                         service_object = self.switchServiceAccount()
    #                         LOGGER.info(f"Got: {reason}, Trying Again.")
    #                         service_object.files().copy(supportsAllDrives=True, fileId=file.get('id'), body=body).execute()

    #                 else:
    #                     raise err
                
    #             except SSLError as e:
    #                 LOGGER.error(str(e))
    #                 service_object = self.switchServiceAccount()
    #                 service_object.files().copy(supportsAllDrives=True, fileId=file.get('id'), body=body).execute()
                
    #             except:
    #                 try:
    #                     self.FileCopythreads.release()
    #                 except:
    #                     pass
    #         else:
    #             status_object.checkFileExist(True)
    #             status_object.set_name(file.get('name'))
    #             LOGGER.info(f"Exisiting file, skipping... Name: {file.get('name')}")
    #     try:
    #         self.FileCopythreads.release()
        
    #     except:
    #         pass
        
    #     return service_object

    
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
            status.SetMainFolder(meta.get('name'), self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(meta.get('id')))
            dest_meta = self.__service.files().get(supportsAllDrives=True, fileId=self.gparentid,
                                              fields="name,id,size").execute()
            status.SetDestinationFolder(dest_meta.get('name'), self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dest_meta.get('id')))
        except Exception as e:
            return f"{str(e).replace('>', '').replace('<', '')}\nMake sure you have access to the file/folder! If using SA, make sure SA group is added to the source!"
        if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE:
            dir_id = self.check_folder_exists(meta.get('name'), self.gparentid)
            if not dir_id:
                dir_id = self.create_directory(meta.get('name'), self.gparentid)
            try:
                self.cloneFolder(meta.get('name'), meta.get('name'), meta.get('id'), dir_id, status, ignoreList)
                for thread in self.threadsList:
                        if thread.is_alive():
                            time.sleep(30)
                            if self.cancelled:
                                return
                            LOGGER.info("Thread still alive, .join()ing with them till the end.")
                            thread.join()
                            LOGGER.info("Thread gracefully exited :D")
                        else:
                            self.threadsList.remove(thread)
                # for thread in self.CopyThreadList:
                #         if thread.is_alive():
                #             LOGGER.info("Thread still alive, .join()ing with them till the end.")
                #             thread.join()
                #         else:
                #             self.CopyThreadList.remove(thread)
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
                file = self.check_file_exists(meta, self.gparentid, self.__service)
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
                if INDEX_URL:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}')
                    msg += f' | <a href="{url}"> Index URL</a>'
            except TypeError:
                pass
        return msg

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError) | retry_if_exception_type(SSLError), before=before_log(LOGGER, logging.DEBUG))
    def cloneFolder(self, name, local_path, folder_id, parent_id, status, ignoreList=[]):
        if self.cancelled:
            return
        temp__service = self.authorize()
        page_token = None
        q = f"'{folder_id}' in parents and trashed=false"
        
        FILES_LIST = []
        FOLDERS_LIST = []

        LOGGER.info(f"Syncing: {local_path}")
        while True:
            try:
                response = temp__service.files().list(includeItemsFromAllDrives=True,
                                                supportsAllDrives=True,
                                                   q=q,
                                                   spaces='drive',
                                                   fields='nextPageToken, files(id, name, mimeType, size, md5Checksum)',
                                                   pageToken=page_token,
                                                   orderBy='modifiedTime desc').execute()
            except HttpError as e:
                LOGGER.error(e)
                raise e

            for file in response.get('files', []):
                if file.get('mimeType') != self.__G_DRIVE_DIR_MIME_TYPE:
                    FILES_LIST.append(file)
                else:
                    FOLDERS_LIST.append(file)

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        if len(FILES_LIST) != 0:
            for filee in FILES_LIST:
                if filee.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                    FOLDERS_LIST.append(filee)
                    continue
                if not self.check_file_exists(filee, parent_id, temp__service):
                    self.copyFile(filee.get('id'), parent_id, status, temp__service)
                    status.checkFileExist(False)
                    self.transferred_size += int(filee.get('size'))
                    status.set_name(filee.get('name'))
                    status.add_size(int(filee.get('size')))
                else:
                    status.set_name(filee.get('name'))
                    status.checkFileExist(True)
        
        try:
            self.threads.release()
        except:
            pass      
        
        for file in FOLDERS_LIST:
            if file.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                file_path = os.path.join(local_path, file.get('name'))
                current_dir_id = self.check_folder_exists(file.get('name'), parent_id, temp__service)
                if not current_dir_id:
                    current_dir_id = self.create_directory(file.get('name'), parent_id, temp__service)
                if not str(file.get('id')) in ignoreList:
                    self.threads.acquire()
                    thr = threading.Thread(target=self.cloneFolder, args=[file.get('name'), file_path, file.get('id'), current_dir_id, status, ignoreList])
                    thr.start()
                    self.threadsList.append(thr)
                    # self.cloneFolder(file.get('name'), file_path, file.get('id'), current_dir_id, status, ignoreList)
                else:
                    LOGGER.info("Ignoring FolderID from clone: " + str(file.get('id')))

        # if len(FILES_LIST) != 0:
        #     for filee in FILES_LIST:
        #         if not self.check_file_exists(filee, parent_id, temp__service):
        #             self.copyFile(filee.get('id'), parent_id, status, temp__service)
        #             status.checkFileExist(False)
        #             self.transferred_size += int(filee.get('size'))
        #             status.set_name(filee.get('name'))
        #             status.add_size(int(filee.get('size')))
        #         else:
        #             status.set_name(filee.get('name'))
        #             status.checkFileExist(True)


        # try:
        #     self.threads.release()
        # except:
        #     pass

        # if self.threads._value < 4:
            # self.threads.release()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError) | retry_if_exception_type(SSLError), before=before_log(LOGGER, logging.DEBUG))
    def listFolderFiles(self, folder_id, service_object=None):
        if not service_object:
            service_object = self.__service
        # service_Temp = self.authorize()
        page_token = None
        q = f"'{folder_id}' in parents"
        files = []
        while True:
            response = service_object.files().list(includeItemsFromAllDrives=True,
                                                supportsAllDrives=True,
                                                   q=q,
                                                   spaces='drive',
                                                   pageSize=200,
                                                   fields='nextPageToken, files(id, name, mimeType, size, md5Checksum)',
                                                   pageToken=page_token).execute()
            for file in response.get('files', []):
                if file.get('mimeType') != "application/vnd.google-apps.folder":
                    files.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        return files
    
    
    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def create_directory(self, directory_name, parent_id, service_object=None):
        if not service_object:
            service_object = self.__service
        file_metadata = {
            "name": directory_name,
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        try:
            file = service_object.files().create(supportsAllDrives=True, body=file_metadata, fields='id').execute()
        except HttpError as e:
            LOGGER.error(e)
            raise e
        file_id = file.get("id")
        if not IS_TEAM_DRIVE:
            self.__set_permission(file_id)
        # LOGGER.info("Created Google-Drive Folder:\nName: {}\nID: {} ".format(file.get("name"), file_id))
        return file_id

    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def check_folder_exists(self, fileName, u_parent_id, service_object=None):
        response = None
        fileName = clean_name(fileName)
        if not service_object:
            service_object = self.__service
        # Create Search Query for API request.
        query = f"'{u_parent_id}' in parents and (name = '{fileName}' and trashed=false)"
        try:
            response = service_object.files().list(includeItemsFromAllDrives=True,
                                                supportsAllDrives=True,
                                                q=query,
                                                spaces='drive',
                                                pageSize=5,
                                                fields='files(id, name, mimeType, size, md5Checksum)',
                                                orderBy='modifiedTime desc').execute()
        except HttpError as e:
            LOGGER.error(e)
            raise e

        if not response:
            raise HttpError
        for file in response.get('files', []):
            if file.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:  # Detect Whether Current Entity is a Folder or File.
                    driveid = file.get('id')
                    # print(file.get('name'))
                    if clean_name(file.get('name')) == fileName:
                        return driveid
                    else:
                        return
    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError) | retry_if_exception_type(SSLError), before=before_log(LOGGER, logging.DEBUG))
    def check_file_exists(self, file, u_parent_id, service_object=None):
        response = None
        fileName = clean_name(file.get('name'))
        if not service_object:
            service_object = self.__service
        # Create Search Query for API request.
        query = f"'{u_parent_id}' in parents and (name contains '{fileName}' and trashed=false)"
        try:
            response = service_object.files().list(includeItemsFromAllDrives=True,
                                                supportsAllDrives=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=5,
                                               fields='files(id, name, mimeType, size, md5Checksum)',
                                               orderBy='modifiedTime desc').execute()
        except HttpError as e:
            LOGGER.error(e)
            raise e

        if not response:
            raise HttpError
        for matched_file in response.get('files', []):
            if matched_file.get('mimeType') != "application/vnd.google-apps.folder":
                    # driveid = file.get('id')
                    if matched_file.get('md5Checksum') == file.get('md5Checksum'):
                        return matched_file
                    else:
                        return False


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