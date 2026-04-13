#!/usr/bin/env python3

# Tool to remove unwanted content (like dynamically inserted ads in podcasts) that isn't in all of a collection of MP3 files.
# Assumes the ad insertion logic is lazy and just pastes frames instead of re-encoding.
# Also assumes you can get copies of the episodes that don't all share any ads.

import sys

from mp3 import good_data

def get_common_chunks(in_streams, out_stream):
    """
    Write only tag blocks and frames common to all the input MP3 streams to the output MP3 stream.
    """

    if len(in_streams) == 0:
        return

    # Collect all ID3 blocks and frames from the first file as a set
    wanted_chunks = set()

    if len(in_streams) > 1:
        for chunk in good_data(in_streams[0]):
            wanted_chunks.add(chunk)
        sys.stderr.write(f"First stream contains {len(wanted_chunks)} frames and tag blocks\n")

    if len(in_streams) > 2:
        for intermediate_stream in in_streams[1:-1]:
            wanted_chunks_observed = set()
            for chunk in good_data(intermediate_stream):
                # Keep wanting only the chunks also in this stream
                if chunk in wanted_chunks:
                    wanted_chunks_observed.add(chunk)
            sys.stderr.write(f"After intermediate stream, {len(wanted_chunks_observed)}/{len(wanted_chunks)} chunks are still wanted\n")
            wanted_chunks = wanted_chunks_observed



    dropped = 0
    total = 0
    for chunk in good_data(in_streams[-1]):
        total += 1
        if len(in_streams) > 1 and chunk not in wanted_chunks:
            dropped += 1
            continue
        out_stream.write(chunk)

    sys.stderr.write(f"Final stream contained {dropped}/{total} frames and tag blocks not in all previous streams\n")
    sys.stderr.write(f"Result stream has {total - dropped} frames and tag blocks\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.stderr.write(f"{sys.argv[0]}: keep only common frames of all MP3 files to standard output\nusage: {sys.agrv[0]} <file_a> <file_b> ...\n")

    get_common_chunks([open(f, 'rb') for f in sys.argv[1:]], sys.stdout.buffer)

