import redis
import os
from collections import OrderedDict
from dotenv import load_dotenv
import httpx
load_dotenv()


_redis = redis.Redis.from_url(os.getenv("REDIS_URL"))
_PDF_TTL = 3600


def get_pdf_bytes(hash: str, url: str) -> bytes:
    key = f"doc:{hash}"

    cached = _redis.hget(key, "pdf_bytes")
    if cached:
        return cached

    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    pdf_bytes = resp.content

    pipe = _redis.pipeline()
    pipe.hset(key, mapping={"pdf_bytes": pdf_bytes})
    pipe.expire(key, _PDF_TTL)
    pipe.execute()

    return pdf_bytes