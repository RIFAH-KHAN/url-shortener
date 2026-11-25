import random
import string 
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

from db import get_connection, init_db

CHARS = string.ascii_letters + string.digits

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # server start hote hi table bana do (agar nahi hai)
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


class ShortenRequest(BaseModel):
    url: HttpUrl


def create_short_url(long_url: str, length: int = 6, max_attempts: int = 5) -> str:
    with get_connection() as conn:
        for _ in range(max_attempts):
            code = "".join(random.choices(CHARS, k=length))
            cur = conn.execute(
                "INSERT INTO urls (short_code, long_url) VALUES (%s, %s) "
                "ON CONFLICT (short_code) DO NOTHING",
                (code, long_url),
            )
            if cur.rowcount == 1:
                return code
    raise RuntimeError("Could not generate a unique code")


@app.post("/shorten")
def shorten(req: ShortenRequest):
    try:
        code = create_short_url(str(req.url))
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Could not create short link")
    return {"short_code": code, "short_url": f"http://localhost:8000/{code}"}


@app.get("/{code}")
def redirect(code: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT long_url FROM urls WHERE short_code = %s", (code,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return RedirectResponse(row[0], status_code=302)