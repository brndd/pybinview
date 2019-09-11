import sys
import os
import logging
import wx
import wx.grid
import wx.lib.intctrl
import struct
import re
import csv

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

        drop = FileDrop()
        self.panel.SetDropTarget(drop)

        pub.subscribe(self.file_structure_prompt, "file_loaded")

        self.command_processor = wx.CommandProcessor()

        self.Bind(event=wx.EVT_MENU_OPEN, handler=self.update_menu_items)

    def create_menu_bar(self):
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        open_file_menu_item = file_menu.Append(wx.ID_OPEN, 'Open File')
        self.Bind(event=wx.EVT_MENU, handler=self.on_open_file, source=open_file_menu_item)
        save_file_menu_item = file_menu.Append(wx.ID_SAVE, 'Export as CSV')
        save_file_menu_item.Enable(False)
        self.Bind(event=wx.EVT_MENU, handler=self.on_save_file, source=save_file_menu_item)
        exit_file_menu_item = file_menu.Append(wx.ID_EXIT, 'Exit')
        self.Bind(event=wx.EVT_MENU, handler=self.on_quit, source=exit_file_menu_item)
        menu_bar.Append(file_menu, '&File')

        edit_menu = wx.Menu()
        undo_edit_menu_item = edit_menu.Append(wx.ID_UNDO, 'Undo\tCtrl+Z')
        undo_edit_menu_item.Enable(False)
        self.Bind(event=wx.EVT_MENU, handler=self.on_undo, source=undo_edit_menu_item)
        redo_edit_menu_item = edit_menu.Append(wx.ID_REDO, 'Redo\tCtrl+Y')
        redo_edit_menu_item.Enable(False)
        self.Bind(event=wx.EVT_MENU, handler=self.on_redo, source=redo_edit_menu_item)
        menu_bar.Append(edit_menu, '&Edit')


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

    #this saves the file into a CSV... for technical reasons (laziness) this breaks the MVC pattern by saving
    #the string data currently in the grid rather than properly manipulating the data in the Model
    #(type conversions would make this too complicated for my tastes)
    def on_save_file(self, event):
        dialog = wx.FileDialog(
            self, message="Save file as CSV...", defaultDir=os.getcwd(),
            defaultFile="", wildcard="CSV files (*.csv)|*.csv", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            logging.debug("Saving CSV into %s", path)
            #I can't believe we have to do it like this
            #TODO: write our own GridTable implementation or properly update the model side of things,
            #so this isn't necessary
            grid = self.panel.grid
            numrows = self.panel.grid.GetNumberRows()
            numcols = self.panel.grid.GetNumberCols()
            rows = []
            for i in range(0, numrows):
                row = []
                for j in range(0, numcols):
                    row.append(grid.GetCellValue(i, j))
                rows.append(row)
            with open(path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                for row in rows:
                    writer.writerow(row)
                logging.debug("Wrote %d rows into %s", len(rows), path)


    def on_quit(self, event):
        dialog = wx.MessageDialog(self, 'Really quit?', 'Confirm quit', wx.YES_NO | wx.NO_DEFAULT)
        if dialog.ShowModal() == wx.ID_YES:
            logging.debug("Exiting program.")
            dialog.Destroy()
            self.Close()

    def on_undo(self, event):
        logging.debug("Undoing")
        self.command_processor.Undo()
        self.update_menu_items()

    def on_redo(self, event):
        logging.debug("Redoing")
        self.command_processor.Redo()
        self.update_menu_items()

    def file_structure_prompt(self, filepath):
        dialog = StructDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            pub.sendMessage("struct_format_selected", struct_format=dialog.format_string)
        dialog.Destroy()

    #this updates the disable/enable state of the menu items appropriately
    def update_menu_items(self, *args, **kwargs):
        if self.panel.grid is not None:
            self.GetMenuBar().FindItemById(wx.ID_SAVE).Enable(True)
        else:
            self.GetMenuBar().FindItemById(wx.ID_SAVE).Enable(False)

        if self.command_processor.CanUndo():
            self.GetMenuBar().FindItemById(wx.ID_UNDO).Enable(True)
        else:
            self.GetMenuBar().FindItemById(wx.ID_UNDO).Enable(False)

        if self.command_processor.CanRedo():
            self.GetMenuBar().FindItemById(wx.ID_REDO).Enable(True)
        else:
            self.GetMenuBar().FindItemById(wx.ID_REDO).Enable(False)



#Drag-and-drop to open a file
class FileDrop(wx.FileDropTarget):
    def OnDropFiles(self, x, y, filenames):
        if len(filenames) > 1:
            logging.error("Received multiple drag-and-drop files, ignoring.")
            return False
        filename = filenames[0]
        logging.debug("Received filename from drag and drop: %s", filename)
        pub.sendMessage("file_selected", filepath=filename)
        return True

#This is the panel/grid that shows the parsed data
class MainPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.grid = None
        self.SetSizer(self.sizer)
        pub.subscribe(self.loadData, "file_parsed")

    def loadData(self, structs):
        #we'll only want to display the grid when data is actually loaded, so it's created here
        if self.grid is None:
            self.grid = wx.grid.Grid(self, wx.ID_ANY)
            self.gridSizer = self.sizer.Add(self.grid, 1, wx.ALL | wx.EXPAND, 5)
            self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.grid_cell_changed)


        logging.debug("Populating list.")
        self.grid.SetTable(None)
        self.grid.CreateGrid(len(structs), len(structs[0]))

        for i, struct in enumerate(structs):
            for j, field in enumerate(struct):
                self.grid.SetCellValue(i, j, str(field))
        self.grid.SetRowLabelSize(wx.grid.GRID_AUTOSIZE)
        self.grid.AutoSize()
        self.Layout() #the scroll bars won't appear without this here...

        self.GetParent().update_menu_items()

    def grid_cell_changed(self, event):
        row = event.GetRow()
        col = event.GetCol()
        old = event.GetString()
        new = self.grid.GetCellValue(row, col)
        command = EditGridText(self.grid, row, col, old, new, canUndo=True, name="Change grid value")
        logging.debug("Grid cell changed, submitting command")

        #not sure if this is the right place for this, but oh well
        self.GetParent().command_processor.Submit(command)
        self.GetParent().update_menu_items()


#Undo-redo functionality is done through these commands
class EditGridText(wx.Command):
    def __init__(self, grid, row, col, oldText, newText, canUndo=False, name=""):
        super().__init__(canUndo, name)
        self.grid = grid
        self.row = row
        self.col = col
        self.oldText = oldText
        self.newText = newText

    def Do(self):
        self.grid.SetCellValue(self.row, self.col, self.newText)
        return True

    def Undo(self):
        self.grid.SetCellValue(self.row, self.col, self.oldText)
        return True


#Struct format selection dialog
#this whole thing is more than a little ugly and could do with refactoring to eg.
#keep the selection state in a more convenient place instead of getting it from the elements
#directly when the selection is accepted... but this will do for now
class StructDialog(wx.Dialog):
    #the values here are a tuple with the length and the struct format character for the type
    _choices = {'char': (1, 'c'),
                'signed char': (1, 'b'),
                'unsigned char': (1, 'B'),
                'boolean': (1, '?'),
                'short': (2, 'h'),
                'unsigned short': (2, 'H'),
                'int': (4, 'i'),
                'unsigned int': (4, 'I'),
                'long': (8, 'q'), #this is actually 'long long' but that's dumb so we're calling it long
                'unsigned long': (8, 'Q'),
                'float': (4, 'f'),
                'double': (8, 'd'),
                'char[]': (1, 's'),
                'null-terminated string': (None, 'S')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #this will contain the format string after a selection has been successfully made
        #it contains None otherwise
        self.format_string = None

        #Smelly UI code below
        self._panel = wx.Panel(self)
        self._sizer = wx.BoxSizer(wx.VERTICAL)

        addSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._add_button = wx.Button(self._panel, id=wx.ID_ADD)
        self._add_button.Bind(wx.EVT_BUTTON, self.add_line)
        addSizer.Add(self._add_button, flag=wx.ALIGN_LEFT)
        self._sizer.Add(addSizer)

        endianSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._rb = wx.RadioBox(self._panel, choices=['Little-endian', 'Big-endian'], majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        endianSizer.Add(self._rb)
        self._sizer.Add(endianSizer)

        buttonSizer = wx.StdDialogButtonSizer()
        self._cancel_button = wx.Button(self._panel, id=wx.ID_CANCEL)
        buttonSizer.AddButton(self._cancel_button)
        self._ok_button = wx.Button(self._panel, id=wx.ID_OK)
        self._ok_button.Bind(wx.EVT_BUTTON, self.on_accept)
        buttonSizer.AddButton(self._ok_button)
        buttonSizer.Realize()
        self._sizer.Add(buttonSizer, flag=wx.ALIGN_BOTTOM|wx.ALIGN_CENTER)

        self.add_line(resize=False)

        self._panel.SetSizer(self._sizer)
        self._sizer.SetSizeHints(self)



    #adds a new line of selection fields
    def add_line(self, event=None, resize=True):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        choices = list(self._choices.keys())
        choice = wx.Choice(self._panel, choices=choices)
        choice.Bind(wx.EVT_CHOICE, self.on_format_selected)
        choice.SetSelection(0)
        sizer.Add(choice)

        sel = choices[choice.GetSelection()]
        length = self._choices[sel][0]
        size = wx.lib.intctrl.IntCtrl(self._panel, value=length, allow_none=True, min=1)
        if sel == 'char[]':
            logging.debug('Enabling size selection.')
            size.Enable(True)
            size.SetNoneAllowed(False)
            size.SetValue(self._choices[sel][0])
        elif sel == 'null-terminated string':
            logging.debug('Disabling size selection.')
            size.SetNoneAllowed(True)
            size.SetValue(None)
            size.Enable(False)
        else:
            size.Enable(False)
            size.SetNoneAllowed(False)
            size.SetValue(self._choices[sel][0])
        sizer.Add(size)

        removeButton = wx.Button(self._panel, id=wx.ID_REMOVE)
        removeButton.Bind(wx.EVT_BUTTON, self.on_delete_clicked)
        sizer.Add(removeButton)

        length = len(self._sizer.GetChildren())
        self._sizer.Insert(length - 3, sizer)
        if resize:
            self._sizer.Layout()
            self._sizer.Fit(self)

    #deletes the clicked selection field
    def on_delete_clicked(self, event):
        sizer = event.GetEventObject().GetContainingSizer()
        self._sizer.Hide(sizer)
        self._sizer.Remove(sizer)
        self._sizer.Layout()
        self._sizer.Fit(self)


    #update the size field to show the size of the selected format (and allow editing if applicable)
    def on_format_selected(self, event):
        text = event.GetString()
        logging.debug('Text is "%s"', text)
        sizer = event.GetEventObject().GetContainingSizer()
        size = sizer.GetChildren()[-2].GetWindow()

        if text == 'char[]':
            logging.debug('Enabling size selection.')
            size.Enable(True)
            size.SetNoneAllowed(False)
            size.SetValue(self._choices[text][0])
        elif text == 'null-terminated string':
            logging.debug('Disabling size selection.')
            size.SetNoneAllowed(True)
            size.SetValue(None)
            size.Enable(False)
        else:
            logging.debug('Disabling size selection.')
            size.Enable(False)
            size.SetNoneAllowed(False)
            size.SetValue(self._choices[text][0])


    #construct the format string before passing the accept
    def on_accept(self, event):
        formatstring = [] #we'll build this in a list and then .join() it because it's faster or summat

        endianness = '<' if self._rb.GetSelection() == 0 else '>'
        formatstring.append(endianness)

        format_sizers = [x.GetSizer() for x in list(self._sizer.GetChildren())[:-3]]
        for sizer in format_sizers:
            format_field = sizer.GetChildren()[0].GetWindow().GetStringSelection()
            format_size = sizer.GetChildren()[1].GetWindow().GetValue()
            format_char = self._choices[format_field][1]
            if format_field == 'char[]':
                formatstring.append(str(format_size))
                formatstring.append(format_char)
            else:
                formatstring.append(format_char)

        self.format_string = ''.join(formatstring)
        logging.debug('Built format string "%s" upon accepting.', self.format_string)
        event.Skip(True)


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
