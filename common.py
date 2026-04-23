#!/usr/bin/env python3

# Tool to remove unwanted content (like dynamically inserted ads in podcasts) that isn't in all of a collection of MP3 files.
# Assumes the ad insertion logic is lazy and just pastes frames instead of re-encoding.
# Also assumes you can get copies of the episodes that don't all share any ads.

import sys
import hashlib
import codecs
import collections

from mp3 import good_data

# We think in terms of "chunks", which are either real MP3 frames or data like MP3 tags.

def hash_chunk(chunk: bytes) -> bytes:
    """
    Produce a representative hash for a chunk that is probably usefully smaller than it.
    """
    # We assume nobody is hash-colliding podcast MP3 frames to annoy us.
    return hashlib.md5(chunk, usedforsecurity=False).digest()

def hash_to_string(chunk_hash: bytes) -> str:
    """
    Produce a hex string from a chunk hash
    """
    return codecs.encode(chunk_hash, "hex").decode("utf-8")

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

def register_appearance(appearances: dict[bytes, ChunkInfo], stream_num: int, chunk_num: int, chunk_hash: bytes):
    """
    Record a chunk appearance in a stream.
    """

    if chunk_hash not in appearances:
        appearances[chunk_hash] = make_info(stream_num, chunk_num)
    else:
        appearances[chunk_hash] = update_info(appearances[chunk_hash], stream_num, chunk_num)

def ad_type(appearances: dict[bytes, ChunkInfo], chunk_hash: bytes, stream_count: int, representative_length: int | None, max_ad_load: float = 0.20, ad_lookup=lambda x: None) -> str | None:
    """
    Return the type of ad this chunk is, or None if not an ad.
    
    The chunk must be registered in appearances.
    
    Queries ad_lookup, which should return True if a hash belongs to a known ad
    in an ad database.
    """
    
    if ad_lookup(chunk_hash):
        # This is a known ad already
        return "Database"
    if len(appearances[chunk_hash].streams) < stream_count:
        # This is an ad because it's not in all versions
        return "Variable"
    if representative_length is not None:
        # We can use shift.
        # Work out  the range of first appearance chunk numbers for this chunk
        location_shift = (appearances[chunk_hash].highest_first_index - appearances[chunk_hash].lowest_first_index) / representative_length
        if location_shift > max_ad_load:
            return "Shift"
            
    return None
        
    

def get_common_chunks(in_streams, out_stream, max_ad_load=0.20, log=lambda x: None, ad_handler=lambda x: None, ad_lookup=lambda x: None):
    """
    Write only tag blocks and frames common to all the input MP3 streams, without too much variation in their loction, to the output MP3 stream.

    Needs to know the maximum plausible ad load in fraction of tag blocks and frames, to identify ads by location shift.
    
    When an ad is found, calls ad_handler with the list of md5 chunk chashes in the ad.
    """

    # TODO: Real alignment or kmer de Bruijn graph to remove frames in ads that also exist in content (like silence).

    if len(in_streams) == 0:
        return
    
    # Collect all chunks as a dict from chunk hash to info for that chunk
    appearances: dict[bytes, ChunkInfo] = {}
    # Collect a set of all chunk hashes persent in all versions
    in_all_versions = None
    # Collec the length in chunks of a representative version
    representative_length = None
    
    # Collect statistics when processing the last stream
    total = 0
    dropped = 0
    ad_count = 0
    
    # Keep a CIGAR string of the last stream
    chunk_map = []
    def append_chunk_map(char):
        if len(chunk_map) == 0 or chunk_map[-1][0] != char:
            chunk_map.append([char, 1])
        else:
            chunk_map[-1][1] += 1
            
    # Keep all the stream hash lists for re-finding ads in earlier streams for
    # the ad handler.
    hash_lists = []
    
    for stream_num, stream in enumerate(in_streams):
        stream_chunks = 0
        variable_stream_chunks = 0
        current_hash_list = []
        current_ad = []
        for i, chunk in enumerate(good_data(stream)):
            h = hash_chunk(chunk)
            stream_chunks += 1
            current_hash_list.append(h)
            
            register_appearance(appearances, stream_num, i, h)
                
            if len(appearances[h].streams) < stream_num + 1:
                variable_stream_chunks += 1
                
            if stream_num == len(in_streams) - 1:
                # This is the final stream, so actually filter.
                # We won't have later occurrences in this stream yet but that's OK.
                total += 1
                
                found = ad_type(appearances, h, len(in_streams), representative_length, max_ad_load, ad_lookup)
                
                if found is not None:
                    dropped += 1
                    append_chunk_map(found[0])
                    current_ad.append(h)
                    continue
                
                append_chunk_map('=')
                out_stream.write(chunk)
                if current_ad:
                    # The ad is over
                    ad_handler(current_ad)
                    ad_count += 1
                    current_ad = []
                    
            if current_ad:
                # An ad was in progress at the end of the stream
                ad_handler(current_ad)
                ad_count += 1
                current_ad = []
        
        if representative_length is None:
            # Remember a length for computing shift
            representative_length = stream_chunks
        
        log(f"Stream {stream_num} contains {variable_stream_chunks}/{stream_chunks} variable chunks")
        
        if stream_num + 1 != len(in_streams):
            # Keep this stream's chunk hash list for reprocessing
            hash_lists.append(current_hash_list)
                
    # TODO: always keep tag blocks?

    log(f"Final stream contained {dropped}/{total} chunks not in all previous streams at coherent locations")
    log(f"Result stream has {total - dropped} chunks")
    log(f"Chunk map:")
    for char, count in chunk_map:
        log(f"{char} x {count}")
    # TODO: We should keep all the hash lists for all the copies, and find and report ads from all of them, not just the final stream.
    log(f"Found {ad_count} ads in final stream")
    
    ad_count = 0
    for hash_list in hash_lists:
        current_ad = []
        for h in hash_list:
            found = ad_type(appearances, h, len(in_streams), representative_length, max_ad_load)
            if found is not None:
                current_ad.append(h)
                continue
            if current_ad:
                # The ad is over
                ad_handler(current_ad)
                ad_count += 1
                current_ad = []
        if current_ad:
            # The ad is over
            ad_handler(current_ad)
            ad_count += 1
            current_ad = []
    log(f"Found {ad_count} ads in previous streams")
        
def cli_ad_handler(ad_chunk_hashes: list[bytes]) -> None:
    """
    Log an ad.
    
    The list of frame hashes must not be empty.
    """
    sys.stderr.write(f"Found ad of {len(ad_chunk_hashes)} frames starting with {hash_to_string(ad_chunk_hashes[0])}\n")

if __name__ == "__main__":

    def log(message):
        sys.stderr.write(f"{message}\n")
    
    if len(sys.argv) < 3:
        log(f"{sys.argv[0]}: keep only common frames of all MP3 files to standard output\nusage: {sys.argv[0]} <file_a> <file_b> ...")
        sys.exit(1)

    get_common_chunks([open(f, "rb") for f in sys.argv[1:]], sys.stdout.buffer, log=log, ad_handler=cli_ad_handler)

