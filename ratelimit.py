import time

import redis

from cache import r

# KEYS[1] = bucket key
# ARGV[1] = capacity, ARGV[2] = refill rate (tokens/sec), ARGV[3] = now (sec)
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil then
  tokens = capacity
  ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) + 1)
return allowed
"""

_script = r.register_script(TOKEN_BUCKET_LUA)


def allow_request(identifier: str, capacity: int = 10, rate: float = 1.0) -> bool:
    try:
        result = _script(
            keys=[f"ratelimit:{identifier}"],
            args=[capacity, rate, time.time()],
        )
        return result == 1
    except redis.RedisError:
        return True  # Redis down ho to users ko block mat karo (fail-open)