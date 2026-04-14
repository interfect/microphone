#!/usr/bin/env python3

# Tool to remove unwanted content (like dynamically inserted ads in podcasts) that isn't in all of a collection of MP3 files.
# Assumes the ad insertion logic is lazy and just pastes frames instead of re-encoding.
# Also assumes you can get copies of the episodes that don't all share any ads.

import sys
import hashlib
import collections

from mp3 import good_data

# We think in terms of "chunks", which are either real MP3 frames or data like MP3 tags.

def hash_chunk(chunk):
    """
    Produce a representative hash for a chunk that is probably usefully smaller than it.
    """
    # We assume nobody is hash-colliding podcast MP3 frames to annoy us.
    return hashlib.md5(chunk, usedforsecurity=False).digest()

# Track each chunk and record total appearances, lowest observed index, highest
# observed index, lowest first index in a stream, and highest first index in a
# stream, plus the set of streams it was observed in.
#
# TODO: We probably only need the first_ variants of the indexes, but I
# couldn't keep them straight, so I overengineered this to track both.
ChunkInfo = collections.namedtuple('ChunkInfo', ['count', 'lowest_index', 'highest_index', 'lowest_first_index', 'highest_first_index', 'streams'])

def make_info(stream_num, index):
    """
    Make a ChunkInfo for a chunk appearing in the given stream at the given index.
    
    We know this is a first appearance of the chunk ever
    """
    return ChunkInfo(1, index, index, index, index, frozenset([stream_num]))

def update_info(info, stream_num, index):
    """
    Return a modified ChunkInfo recording an additional appearance in the given stream at the given index.
    """
    first_in_stream = stream_num not in info.streams
    return ChunkInfo(
        info.count + 1,
        min(index, info.lowest_index),
        max(index, info.highest_index),
        min(index, info.lowest_first_index) if first_in_stream else info.lowest_first_index,
        max(index, info.highest_first_index) if first_in_stream else info.highest_first_index,
        info.streams.union(frozenset([stream_num])) if first_in_stream else info.streams,
    )

def get_common_chunks(in_streams, out_stream, max_ad_load=0.20, log=lambda x: None):
    """
    Write only tag blocks and frames common to all the input MP3 streams, without too much variation in their loction, to the output MP3 stream.

    Needs to know the maximum plausible ad load in fraction of tag blocks and frames, to identify ads by location shift.
    """

    # TODO: Real alignment or kmer de Bruijn graph to remove frames in ads that also exist in content (like silence).

    if len(in_streams) == 0:
        return
    
    # Collect all chunks as a dict from chunk hash to first observed chunk number list
    appearances = {}
    # Collect a set of all chunk hashes persent in all versions
    in_all_versions = None
    # Collec the length in chunks of a representative version
    representative_length = None
    
    # Collect statistics when processing the last stream
    total = 0
    dropped = 0
    shifted = 0
    min_shift_removed = None
    max_shift_removed = None
    
    # Keep a CIGAR string of the last stream
    chunk_map = []
    def append_chunk_map(char):
        if len(chunk_map) == 0 or chunk_map[-1][0] != char:
            chunk_map.append([char, 1])
        else:
            chunk_map[-1][1] += 1
    
    for stream_num, stream in enumerate(in_streams):
        stream_chunks = 0
        variable_stream_chunks = 0
        for i, chunk in enumerate(good_data(stream)):
            h = hash_chunk(chunk)
            stream_chunks += 1
            if h not in appearances:
                appearances[h] = make_info(stream_num, i)
            else:
                appearances[h] = update_info(appearances[h], stream_num, i)
                
            if len(appearances[h].streams) < stream_num + 1:
                variable_stream_chunks += 1
                
            if stream_num == len(in_streams) - 1:
                # This is the final stream, so actually filter.
                # We won't have later occurrences in this stream yet but that's OK.
                total += 1
                
                if stream_num > 0:
                    # We can use presence in all versions
                    if len(appearances[h].streams) < stream_num + 1:
                        # This was only in some versions
                        dropped += 1
                        append_chunk_map(str(len(appearances[h].streams)))
                        continue
                
                if representative_length is not None:
                    # We can use shift.
                    # Work out  the range of first appearance chunk numbers for this chunk
                    location_shift = (appearances[h].highest_first_index - appearances[h].lowest_first_index) / representative_length
                    if location_shift > max_ad_load:
                        # This frame appeared in everything but at a wildly variable location: probably an ad
                        shifted += 1
                        dropped += 1
                        if min_shift_removed is None or min_shift_removed > location_shift:
                            min_shift_removed = location_shift
                        if max_shift_removed is None or max_shift_removed < location_shift:
                            max_shift_removed = location_shift
                        append_chunk_map('S')
                        continue
                
                append_chunk_map('=')
                out_stream.write(chunk)
        
        if representative_length is None:
            # Remember a length for computing shift
            representative_length = stream_chunks
        
        log(f"Stream {stream_num} contains {variable_stream_chunks}/{stream_chunks} variable chunks")
                
    # TODO: always keep tag blocks?

    log(f"Final stream contained {dropped}/{total} chunks not in all previous streams at coherent locations")
    if shifted > 0:
        log(f"Of which {shifted} were in all previous streams at excessively variable locations ({min_shift_removed} to {max_shift_removed})")
    log(f"Result stream has {total - dropped} chunks")
    log(f"Chunk map:")
    for char, count in chunk_map:
        log(f"{char} x {count}")


if __name__ == "__main__":

    def log(message):
        sys.stderr.write(f"{message}\n")
    
    if len(sys.argv) < 3:
        log(f"{sys.argv[0]}: keep only common frames of all MP3 files to standard output\nusage: {sys.agrv[0]} <file_a> <file_b> ...")

    get_common_chunks([open(f, 'rb') for f in sys.argv[1:]], sys.stdout.buffer, log=log)

