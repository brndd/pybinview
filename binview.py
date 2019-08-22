import sys
import logging
import wx
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
        self.struct_format = struct_format
        #we need re for this because str.split() isn't smart enough
        split_format = list(filter(None, re.split(r"(S)", struct_format)))
        logging.debug('struct_format split into %d parts.', len(split_format))
        #TODO: for now our field (column) names are just these identifiers
        self.field_names = split_format

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

            parsed_structs.append(current_struct) #we don't want to append incomplete stuff, I guess
        self.structs = parsed_structs



logging.basicConfig(level=logging.DEBUG)
if __name__ == '__main__':
    if sys.argv[1] == 'debug':
        logging.basicConfig(level=logging.DEBUG)
        useNotifyByWriteFile(sys.stdout)
    else:
        logging.basicConfig(level=logging.INFO)
    logging.debug('Initializing application.')
    app = wx.App()
    app.MainLoop()
