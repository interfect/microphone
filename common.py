#!/usr/bin/env python3

# Tool to remove unwanted content (like dynamically inserted ads in podcasts) that isn't in all of a collection of MP3 files.
# Assumes the ad insertion logic is lazy and just pastes frames instead of re-encoding.
# Also assumes you can get copies of the episodes that don't all share any ads.

import sys

from mp3 import good_data

def get_common_chunks(in_streams, out_stream, max_ad_load=0.20):
    """
    Write only tag blocks and frames common to all the input MP3 streams, without too much variation in their loction, to the output MP3 stream.

    Needs to know the maximum plausible ad load in fraction of tag blocks and frames, to identify ads by location shift.
    """

    # TODO: Real alignment or kmer de Bruijn graph to remove frames in ads that also exist in content (like silence).

    if len(in_streams) == 0:
        return

    # Collect all ID3 blocks and frames as a dict from possibly-wanted chunk to first observed chunk number list
    wanted_chunks = {}

    if len(in_streams) > 1:
        for i, chunk in enumerate(good_data(in_streams[0])):
            if chunk not in wanted_chunks:
                # Track only first appearance
                wanted_chunks[chunk] = [i]
        sys.stderr.write(f"First stream contains {len(wanted_chunks)} frames and tag blocks\n")

    representative_length = len(wanted_chunks)

    if len(in_streams) > 2:
        for stream_num in range(1, len(in_streams) - 1):
            intermediate_stream = in_streams[stream_num]
            for i, chunk in enumerate(good_data(intermediate_stream)):
                # Keep wanting only the chunks also in this stream
                if chunk in wanted_chunks and len(wanted_chunks[chunk]) < stream_num + i:
                    # Track only first appearance
                    wanted_chunks[chunk].append(i)
            # Drop any chunks that didn't appear in all streams so far
            wanted_chunks = {k: v for k, v in wanted_chunks.items() if len(v) == stream_num + 1}

            sys.stderr.write(f"After middle stream {stream_num}, {len(wanted_chunks)} chunks are still wanted\n")

    dropped = 0
    total = 0
    for i, chunk in enumerate(good_data(in_streams[-1])):
        total += 1
        if len(in_streams) > 1:
            if chunk not in wanted_chunks:
                dropped += 1
                continue
            if len(wanted_chunks[chunk]) < len(in_streams):
                # Track only first appearance
                wanted_chunks[chunk].append(i)
            # Work out  the range of first appearance chunk numbers for this chunk
            min_location = min(wanted_chunks[chunk])
            max_location = max(wanted_chunks[chunk])
            location_shift = (max_location - min_location) / representative_length
            if location_shift > max_ad_load:
                # This frame appeared in everything but at a wildly variable location: probably an ad
                sys.stderr.write(f"Dropping common frame or tag block that ranged in first position from {min_location} to {max_location}\n")
                dropped += 1
                continue

        out_stream.write(chunk)

    # TODO: always keep tag blocks?

    sys.stderr.write(f"Final stream contained {dropped}/{total} frames and tag blocks not in all previous streams at coherent locations\n")
    sys.stderr.write(f"Result stream has {total - dropped} frames and tag blocks\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.stderr.write(f"{sys.argv[0]}: keep only common frames of all MP3 files to standard output\nusage: {sys.agrv[0]} <file_a> <file_b> ...\n")

    get_common_chunks([open(f, 'rb') for f in sys.argv[1:]], sys.stdout.buffer)

