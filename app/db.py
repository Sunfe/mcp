import sqlite3
from app.config import settings


def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        path TEXT NOT NULL UNIQUE,
        file_type TEXT,
        category TEXT,
        file_mtime REAL,
        file_size INTEGER,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        source_info TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        content,
        chunk_id UNINDEXED,
        document_id UNINDEXED
    )
    """)

    conn.commit()
    conn.close()
