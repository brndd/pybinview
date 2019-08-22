import random
import struct
import csv

random.seed()
with open('testdata.dat', 'wb') as f, open('testdata.csv', 'w', newline='') as csvf:
    words = b"The contents of this string don't really matter.\0"
    structstring = f"<chiq{len(words)}sd" #unsigned_char short int long string double
    the_struct = struct.Struct(structstring)
    csvwriter = csv.writer(csvf, quoting=csv.QUOTE_NONNUMERIC)
    for i in range(10):
        #alright this is stupid but it works... assuming your random implementation has getrandbits()
        chiqd = struct.unpack("<chiqd", random.getrandbits(23*8).to_bytes(23, byteorder='little'))
        random_struct = the_struct.pack(*chiqd[:4], words, chiqd[4])
        f.write(random_struct)
        csvwriter.writerow((ord(chiqd[0]), chiqd[1], chiqd[2], chiqd[3], words[:-1].decode('ascii'), chiqd[4]))
