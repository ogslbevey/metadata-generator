import redis
import os
from collections import OrderedDict

_redis = redis.Redis.from_url(os.getenv("REDIS_URL"))
_PDF_TTL = 3600  # match your result_expires
_pdf_cache: OrderedDict[str, bytes] = OrderedDict()
_CACHE_MAX = 3  # how many different docs to keep per process

def get_pdf_bytes(hash: str, url: str) -> bytes:
    if hash in _pdf_cache:
        _pdf_cache.move_to_end(hash)
        return _pdf_cache[hash]

    cached = _redis.hget(f"doc:{hash}", "pdf_bytes")   # hget, not get
    if cached:
        _pdf_cache[hash] = cached
        _pdf_cache.move_to_end(hash)
        return cached

    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    pdf_bytes = resp.content

    # fallback store must ALSO be hset, to keep the type consistent
    _redis.hset(f"doc:{hash}", mapping={"pdf_bytes": pdf_bytes})
    _redis.expire(f"doc:{hash}", _PDF_TTL)

    while len(_pdf_cache) >= _CACHE_MAX:
        _pdf_cache.popitem(last=False)
    _pdf_cache[hash] = pdf_bytes
    return pdf_bytes