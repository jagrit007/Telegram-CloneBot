from bot.fs_utils import get_readable_file_size

class CloneStatus:
    def __init__(self, size=0):
        self.size = size
        self.name = ''
        self.status = False
        self.checking = False
        self.MainFolderName = ''
        self.MainFolderLink = ''
        self.DestinationFolderName = ''
        self.DestinationFolderLink = ''


    def get_size(self):
        return get_readable_file_size(int(self.size))
    
    def add_size(self, value):
        self.size += int(value)

    def set_name(self, name=''):
        self.name = name

    def get_name(self):
        return self.name
    
    def set_status(self, stat):
        self.status = stat
    
    def done(self):
        return self.status

    def checkFileExist(self, checking=False):
        self.checking = checking

    def checkFileStatus(self):
        return self.checking

    def SetMainFolder(self, folder_name, link):
        self.MainFolderName = folder_name
        self.MainFolderLink = link

    def SetDestinationFolder(self, folder_name, link):
        self.DestinationFolderName = folder_name
        self.DestinationFolderLink = link