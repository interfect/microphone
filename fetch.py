#!/usr/bin/env python3

# Fetch script to get several distinct copies of an episode out of Megaphone and filter down to an ad-free copy.

import sys
import urllib.request
import tempfile
import shutil
import random

from common import get_common_chunks


def stream_clean(traffic_url, out_stream, log=lambda x: None):
    """
    Given a Megaphone URL, stream a clean version of it to the given writable, with dynamic ads removed.
    """
    
    # TODO: It would be nice if this was a context manager on a readable, but
    # then we'd have to implement all or logic as a read method
    
    # How many variants of the episode should we look for?
    MIN_HEAD_COUNT = 5
    MAX_HEAD_COUNT = 20
    MIN_DISTINCT = 5

    if not traffic_url.startswith('https://traffic.megaphone.fm/'):
        raise RuntimeError("Not a supported URL")

    base_url = traffic_url.split('?')[0]

    # HEAD with several updated times and collect distinct sizes
    size_to_url = {}
    try_number = 0
    while try_number < MAX_HEAD_COUNT and (try_number < MIN_HEAD_COUNT or len(size_to_url) < MIN_DISTINCT):
        # Every time we fetch a URL (from an IP?), Megaphone generates and caches a
        # distinct cut of the episode, with (hopefully) different ads. We get the
        # same one later (much faster) when we ask for the same URL.
        # We use a plausible magic number timestamp in the cache buster.
        try_url = f"{base_url}?updated={1671149327 + try_number}"
        try_number += 1
        req = urllib.request.Request(url=try_url, method='HEAD')
        with urllib.request.urlopen(req) as f:
            if f.status != 200:
                # We didn't get this one. Drop it.
                log(f"{try_url} was not available ({f.status})")
                continue
            size = f.headers["Content-Length"]
            log(f"{try_url} has size {size}")
            if size not in size_to_url:
                # This is a novel file because it is a novel size
                size_to_url[size] = try_url

    log(f"Found {len(size_to_url)}/{try_number} distinct versions")

    # Fetch all distinct sizes
    files_to_intersect = []
    for url in size_to_url.values():
        # Don't bother storing to a temp file for now.
        files_to_intersect.append(urllib.request.urlopen(url))
    
    # Filter down to common frames
    get_common_chunks(files_to_intersect, out_stream, log=log)

def open_clean(traffic_url, log=lambda x: None):
    """
    Given a Megaphone URL, returns a stream of a clean version, with dynamic ads removed.
    
    Any temporary files will be cleaned up when the stream is closed.
    """
    
    out_file = tempfile.TemporaryFile(suffix='.mp3')
    stream_clean(traffic_url, out_file, log=log)
    out_file.seek(0)
    return out_file

if __name__ == "__main__":

    def log(message):
        sys.stderr.write(f"{message}\n")
    
    if len(sys.argv) != 2:
        log(f"{sys.argv[0]}: get a clean copy of a Megaphone podcast episode without dynamic ads to standard out\nusage: {sys.argv[0]} https://traffic.megaphone.fm/<...>")

    result_file = open_clean(sys.argv[1], log=log)
    shutil.copyfileobj(result_file, sys.stdout.buffer)








