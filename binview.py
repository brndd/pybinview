import sys
import os
import logging
import wx
import wx.grid
import struct
import re

from pubsub import pub
from pubsub.utils.notification import useNotifyByWriteFile

class Model:
    def __init__(self):
        self._binary_data = None
        self.filepath = None
        self.structs = []
        self.field_names = []
        self.struct_format = None

    def loadFile(self, filepath):
        self.filepath = filepath
        logging.debug('Loading file %s', filepath)
        with open(filepath, 'rb') as f:
            self._binary_data = f.read()
        logging.debug('Read %d bytes from file %s', len(self._binary_data), filepath)
        pub.sendMessage("file_loaded", filepath=filepath)

    #This takes a struct format similar to the struct class.
    #The only difference is that a capital S is parsed as an arbitrary-length null-terminated string
    def parseFile(self, struct_format):
        logging.debug('Attempting to parse with struct_format %s.', struct_format)
        if struct_format is None:
            logging.debug('struct_format was None, not parsing.')
            return

        if struct_format[0] in ('@', '=', '<', '>', '!'):
            prefix = struct_format[0]
            struct_format = struct_format[1:]
        else:
            prefix = '<'
        self.struct_format = struct_format
        #we need re for this because str.split() isn't smart enough
        split_format = list(filter(None, re.split(r"(S)", struct_format)))
        logging.debug('struct_format split into %d parts.', len(split_format))


        #actually parse the data
        offset = 0 #current position in the bytes array
        parsed_structs = []
        data_length = len(self._binary_data)
        while offset < data_length:
            current_struct = []
            for part in split_format:
                #null-terminated strings need to be read bit by bit because struct lacks this functionality
                #this probably isn't the most pythonic way of doing it, let alone the prettiest, but eh...
                if part == "S":
                    string_bytearray = bytearray()
                    while offset < data_length:
                        char = self._binary_data[offset]
                        offset += 1
                        if char == 0: #don't want to include the null character
                            break
                        else:
                            string_bytearray.append(char)
                    s = str(struct.unpack(f"{len(string_bytearray)}s", string_bytearray)[0], encoding='UTF-8')
                    logging.debug("Read string \"%s\" from data.", s)
                    current_struct.append(s)
                #otherwise we just use struct's built-in facilities to read all the data except null-terminated strings
                else:
                    size = struct.calcsize('<'+part)
                    if (offset + size) > data_length:
                        #since there's no more data left, pad the rest of the struct with Nones
                        #we may be throwing some out, but whatever...
                        logging.debug("Reached end of data so reading nulls.")
                        current_struct += [None for x in part]
                    else:
                        l = list(struct.unpack_from('<'+part, self._binary_data, offset))
                        logging.debug("Read %d values from data: %s", len(l), str(l))
                        current_struct += l
                    offset += size
            parsed_structs.append(current_struct)
        self.structs = parsed_structs
        pub.sendMessage("file_parsed", structs=parsed_structs)


class Controller:
    def __init__(self):
        self.model = Model()
        self.view = MainView()
        self.view.Show()

        pub.subscribe(self.open_file, "file_selected")
        pub.subscribe(self.parse_file, "struct_format_selected")

    def open_file(self, filepath):
        self.model.loadFile(filepath)

    def parse_file(self, struct_format):
        self.model.parseFile(struct_format)

#This is the main Frame for the GUI
class MainView(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Binary Viewer", size=(800,600))
        self.create_menu_bar()
        self.panel = MainPanel(self)

        pub.subscribe(self.file_structure_prompt, "file_loaded")

    def create_menu_bar(self):
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        open_file_menu_item = file_menu.Append(wx.ID_ANY, 'Open File')
        menu_bar.Append(file_menu, '&File')
        self.Bind(
            event=wx.EVT_MENU,
            handler=self.on_open_file,
            source=open_file_menu_item
        )
        self.SetMenuBar(menu_bar)

    def on_open_file(self, event):
        dialog = wx.FileDialog(
            self, message="Open File", defaultDir=os.getcwd(),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            logging.debug("Got path from open dialog: %s", path)
            pub.sendMessage("file_selected", filepath=path)

        dialog.Destroy()

    def file_structure_prompt(self, filepath):
        dialog = wx.TextEntryDialog(self, "Input struct format string.")
        if dialog.ShowModal() == wx.ID_OK:
            pub.sendMessage("struct_format_selected", struct_format=dialog.GetValue())
        dialog.Destroy()

#This is the panel/list that shows the parsed data
class MainPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.grid = wx.grid.Grid(self, wx.ID_ANY)
        #self.grid.EnableEditing(False)
        self.gridSizer = self.sizer.Add(self.grid, 1, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(self.sizer)
        pub.subscribe(self.loadData, "file_parsed")

    def loadData(self, structs):
        logging.debug("Populating list.")
        self.grid.SetTable(None)
        self.grid.CreateGrid(len(structs), len(structs[0]))

        for i, struct in enumerate(structs):
            for j, field in enumerate(struct):
                self.grid.SetCellValue(i, j, str(field))

class MyGrid(wx.grid.Grid):
    def __init__(self, parent):
        super().__init__(self, parent)




if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'debug':
        logging.basicConfig(level=logging.DEBUG)
        useNotifyByWriteFile(sys.stdout)
    else:
        logging.basicConfig(level=logging.INFO)
    logging.debug('Initializing application.')
    app = wx.App()
    c = Controller()
    app.MainLoop()
