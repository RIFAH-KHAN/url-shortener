import os

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = 3600  # 1 hour

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_cached_url(code: str):
    try:
        return r.get(f"url:{code}")
    except redis.RedisError:
        return None


def set_cached_url(code: str, long_url: str, ttl: int = CACHE_TTL_SECONDS):
    if ttl <= 0:
        return
    try:
        r.set(f"url:{code}", long_url, ex=ttl)
    except redis.RedisError:
        pass