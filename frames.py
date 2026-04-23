#!/usr/bin/env python3

# Turn an MP3 file into a list of frame/tag block hashes

import sys

from mp3 import good_data
from common import hash_chunk, hash_to_string

if __name__ == "__main__":

    def log(message):
        sys.stderr.write(f"{message}\n")
    
    if len(sys.argv) != 2:
        log(f"{sys.argv[0]}: get chunk hashes to standard output\nusage: {sys.agrv[0]} <file>")
        sys.exit(1)

    for chunk in good_data(open(sys.argv[1], "rb")):
        print(hash_to_string(hash_chunk(chunk)))

