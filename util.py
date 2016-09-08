from lru import LRUCacheDict

_dircache = LRUCacheDict(max_size=30, expiration=30*60)
