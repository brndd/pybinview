import wx

class BinviewFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Binary Viewer")
        self.Show()

if __name__ == '__main__':
    app = wx.App()
    frame = BinviewFrame()
    app.MainLoop()
