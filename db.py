# db.py: global ad database

from typing import IO
import io
import json
import base64
import gzip

class StaticAdDatabase:
    """
    Class-scope database of known ads
    
    Stored in memory, because there can't be *that* many ads, right?
    """
    
    # This stores all ad chunk hashes for quick lookup
    ad_chunks: set[bytes] = set()
    # This stores all ads as tuples
    ads: set[tuple] = set()
    
    @classmethod
    def load(cls, stream: IO[bytes]) -> None:
        """
        Load ads from the given JSON stream.
        """
        gzip_stream = gzip.GzipFile(fileobj=stream, mode="rb")
        text_stream = io.TextIOWrapper(gzip_stream, encoding="utf-8")
        db_in = json.load(text_stream)
        for ad in db_in:
            # Put all the ads in the database after decoding the hashes
            cls.insert([base64.b64decode(h.encode("utf-8")) for h in ad])
        # Don't close the backing stream
        text_stream.detach()
        gzip_stream.close()
        
        
    @classmethod
    def save(cls, stream: IO[bytes]) -> None:
        """
        Save ads to the given JSON stream.
        """
        
        gzip_stream = gzip.GzipFile(fileobj=stream, mode="wb")
        text_stream = io.TextIOWrapper(gzip_stream, encoding="utf-8")
        
        def convert(o):
            """
            Convert database objects to what JSON can serialize.
            """
            if isinstance(o, (set, tuple)):
                # Convert sets and tuples to JSON arrays
                return list(o)
            elif isinstance(o, bytes):
                # Convert bytes to base64-encoded strings
                return base64.b64encode(o).decode("utf-8")
            else:
                # Keep same type
                return o

        json.dump(cls.ads, text_stream, default=convert, indent=2)
        text_stream.flush()
        gzip_stream.flush()
        # Don't close the backing stream
        text_stream.detach()
        gzip_stream.close()
        
    @classmethod
    def lookup(cls, chunk_hash: bytes) -> bool:
        """
        Determine if the given chunk hash belongs to an ad.
        """
        return chunk_hash in cls.ad_chunks
    
    @classmethod
    def insert(cls, hash_list: list[bytes]) -> None:
        """
        Add an add as a list of frame hashes to the database.
        """
        hash_tuple = tuple(hash_list)
        if hash_tuple not in cls.ads:
            # Remember this new ad
            cls.ads.add(hash_tuple)
            for h in hash_tuple:
                # And all its chunks
                cls.ad_chunks.add(h)
        
