import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

from auth.db import get_db, init_db

router = APIRouter()
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Initialise DB tables on module load
init_db()


# ── Pydantic models ──────────────────────────────────────────────

class AuthPayload(BaseModel):
    username: str
    password: str


class FileHistoryPayload(BaseModel):
    username: str
    filename: str
    content: str


class SearchPayload(BaseModel):
    query: str


# ── Auth endpoints ───────────────────────────────────────────────

@router.post("/register")
@router.post("/signup")
def register(payload: AuthPayload):
    username = payload.username.strip()
    password = payload.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    pw_hash = _pwd_ctx.hash(password)
    try:
        with get_db() as con:
            con.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, pw_hash),
            )
            con.commit()
    except Exception:
        raise HTTPException(status_code=400, detail="Username already exists.")
    return {"message": "User created successfully.", "username": username}


@router.post("/login")
def login(payload: AuthPayload):
    username = payload.username.strip()
    password = payload.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    with get_db() as con:
        row = con.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row or not _pwd_ctx.verify(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"message": "Login successful.", "username": row["username"]}


# ── File history endpoints ───────────────────────────────────────

@router.post("/history")
def save_file_history(payload: FileHistoryPayload):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db() as con:
        # Upsert
        con.execute(
            """
            INSERT INTO file_history (username, filename, content, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username, filename) DO UPDATE SET
                content    = excluded.content,
                updated_at = excluded.updated_at
            """,
            (payload.username, payload.filename, payload.content, now),
        )
        # Enforce max 5 entries per user (delete oldest)
        con.execute(
            """
            DELETE FROM file_history
            WHERE username = ? AND id NOT IN (
                SELECT id FROM file_history
                WHERE username = ?
                ORDER BY updated_at DESC
                LIMIT 5
            )
            """,
            (payload.username, payload.username),
        )
        con.commit()
    return {"message": "File history updated."}


@router.get("/history/{username}")
def get_file_history(username: str):
    with get_db() as con:
        rows = con.execute(
            """
            SELECT id, filename, content, updated_at
            FROM file_history
            WHERE username = ?
            ORDER BY updated_at DESC
            """,
            (username,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Search history endpoints ─────────────────────────────────────

@router.get("/search-history")
def get_search_history():
    with get_db() as con:
        rows = con.execute(
            "SELECT id, query, created_at FROM search_history ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/search-history")
def add_search_history(payload: SearchPayload):
    q = payload.query.strip()
    if not q:
        return {"ok": False}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db() as con:
        con.execute(
            "INSERT INTO search_history (query, created_at) VALUES (?, ?) "
            "ON CONFLICT(query) DO UPDATE SET created_at = excluded.created_at",
            (q, now),
        )
        con.commit()
    return {"ok": True}


@router.delete("/search-history/{item_id}")
def delete_search_history(item_id: int):
    with get_db() as con:
        con.execute("DELETE FROM search_history WHERE id = ?", (item_id,))
        con.commit()
    return {"ok": True}
