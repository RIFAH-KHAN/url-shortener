import random
import string
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, HttpUrl

from cache import CACHE_TTL_SECONDS, get_cached_url, set_cached_url
from db import get_connection, init_db

CHARS = string.ascii_letters + string.digits


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


class ShortenRequest(BaseModel):
    url: HttpUrl
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


def create_short_url(
    long_url: str,
    expires_at: Optional[datetime],
    length: int = 6,
    max_attempts: int = 5,
) -> str:
    with get_connection() as conn:
        for _ in range(max_attempts):
            code = "".join(random.choices(CHARS, k=length))
            cur = conn.execute(
                "INSERT INTO urls (short_code, long_url, expires_at) "
                "VALUES (%s, %s, %s) ON CONFLICT (short_code) DO NOTHING",
                (code, long_url, expires_at),
            )
            if cur.rowcount == 1:
                return code
    raise RuntimeError("Could not generate a unique code")


def log_click(code: str, request: Request):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO clicks (short_code, user_agent, referer) "
            "VALUES (%s, %s, %s)",
            (
                code,
                request.headers.get("user-agent"),
                request.headers.get("referer"),
            ),
        )


@app.post("/shorten")
def shorten(req: ShortenRequest):
    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)
    try:
        code = create_short_url(str(req.url), expires_at)
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Could not create short link")
    return {
        "short_code": code,
        "short_url": f"http://localhost:8000/{code}",
        "expires_at": expires_at,
    }


@app.get("/stats/{code}")
def stats(code: str):
    with get_connection() as conn:
        url_row = conn.execute(
            "SELECT long_url, created_at, expires_at FROM urls WHERE short_code = %s",
            (code,),
        ).fetchone()
        if url_row is None:
            raise HTTPException(status_code=404, detail="Link not found")
        total = conn.execute(
            "SELECT COUNT(*) FROM clicks WHERE short_code = %s", (code,)
        ).fetchone()[0]
        per_day = conn.execute(
            "SELECT date_trunc('day', clicked_at)::date AS day, COUNT(*) "
            "FROM clicks WHERE short_code = %s "
            "GROUP BY day ORDER BY day DESC LIMIT 7",
            (code,),
        ).fetchall()
    return {
        "short_code": code,
        "long_url": url_row[0],
        "created_at": url_row[1],
        "expires_at": url_row[2],
        "total_clicks": total,
        "clicks_last_7_days": [{"date": str(d), "clicks": c} for d, c in per_day],
    }


@app.get("/{code}")
def redirect(code: str, request: Request):
    # 1. Cache me dhundo
    long_url = get_cached_url(code)
    if long_url:
        log_click(code, request)
        return RedirectResponse(long_url, status_code=302, headers={"X-Cache": "HIT"})

    # 2. Cache miss: database se lo
    with get_connection() as conn:
        row = conn.execute(
            "SELECT long_url, expires_at FROM urls WHERE short_code = %s", (code,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Link not found")

    long_url, expires_at = row

    # 3. Expiry check
    ttl = CACHE_TTL_SECONDS
    if expires_at is not None:
        remaining = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        if remaining <= 0:
            raise HTTPException(status_code=410, detail="Link has expired")
        ttl = min(CACHE_TTL_SECONDS, remaining)

    # 4. Cache me save (expiry se zyada der nahi) aur click log
    set_cached_url(code, long_url, ttl)
    log_click(code, request)
    return RedirectResponse(long_url, status_code=302, headers={"X-Cache": "MISS"})