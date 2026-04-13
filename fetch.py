#!/usr/bin/env python3

# Fetch script to get several distinct copies of an episode out of Megaphone and filter down to an ad-free copy.

import sys
import urllib.request
import tempfile
import shutil
import random

from common import get_common_chunks


def open_clean(traffic_url):
    """
    Given a Megaphone URL, returns a tempfile stream of a clean version, with dynamic ads removed.
    """

    HEAD_COUNT = 5

    if not traffic_url.startswith('https://traffic.megaphone.fm/'):
        raise RuntimeError("Not a supported URL")

    base_url = traffic_url.split('?')[0]

    # HEAD with several updated times and collect distinct sizes
    size_to_url = {}
    for i in range(HEAD_COUNT):
        # Every time we fetch a URL (from an IP?), Megaphone generates and caches a
        # distinct cut of the episode, with (hopefully) different ads. We get the
        # same one later (much faster) when we ask for the same URL.
        # We use a plausible magic number timestamp in the cache buster.
        try_url = f"{base_url}?updated={1671149327 + i}"
        req = urllib.request.Request(url=try_url, method='HEAD')
        with urllib.request.urlopen(req) as f:
            size = f.headers["Content-Length"]
            sys.stderr.write(f"{try_url} has size {size}\n")
            if size not in size_to_url:
                # This is a novel file because it is a novel size
                size_to_url[size] = try_url

    sys.stderr.write(f"Found {len(size_to_url)}/{HEAD_COUNT} distinct versions\n")

    # Fetch all distinct sizes
    files_to_intersect = []
    for url in size_to_url.values():
        # Don't bother storing to a temp file for now.
        files_to_intersect.append(urllib.request.urlopen(url))

    # Filter down to common frames
    out_file = tempfile.TemporaryFile(suffix='.mp3')
    get_common_chunks(files_to_intersect, out_file)
    return out_file

if __name__ == "__main__":

    if len(sys.argv) != 2:
        sys.stderr.write(f"{sys.argv[0]}: get a clean copy of a Megaphone podcast episode without dynamic ads to standard out\nusage: {sys.argv[0]} https://traffic.megaphone.fm/<...>\n")

    result_file = open_clean(sys.argv[1])
    result_file.seek(0)
    shutil.copyfileobj(result_file, sys.stdout.buffer)








