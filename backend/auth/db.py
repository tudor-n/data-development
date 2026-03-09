import sqlite3
import pathlib

_DB_PATH = pathlib.Path(__file__).parent.parent / "clarifi.db"


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(str(_DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS file_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL,
                filename   TEXT NOT NULL,
                content    TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(username, filename)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                query      TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        con.commit()
