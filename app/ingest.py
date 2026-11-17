from pathlib import Path
from datetime import datetime
import os

from app.config import settings
from app.db import get_conn, init_db
from app.parsers import extract_text


def chunk_text(text: str, chunk_size: int, overlap: int):
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def file_category(path: Path, raw_dir: Path) -> str:
    try:
        rel = path.relative_to(raw_dir)
        if len(rel.parts) > 1:
            return rel.parts[0]
    except Exception:
        pass
    return "default"


def ingest_one(conn, path: Path, raw_dir: Path):
    stat = path.stat()
    text = extract_text(path)

    if not text.strip():
        print(f"[SKIP] empty or unsupported: {path}")
        return

    title = path.name
    category = file_category(path, raw_dir)
    now = datetime.utcnow().isoformat()

    cur = conn.cursor()

    cur.execute("SELECT id, file_mtime, file_size FROM documents WHERE path = ?", (str(path),))
    old = cur.fetchone()

    if old and float(old[1]) == float(stat.st_mtime) and int(old[2]) == int(stat.st_size):
        print(f"[UNCHANGED] {path}")
        return

    if old:
        document_id = old[0]
        cur.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        cur.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
        cur.execute("""
            UPDATE documents
            SET title=?, file_type=?, category=?, file_mtime=?, file_size=?, updated_at=?
            WHERE id=?
        """, (
            title, path.suffix.lower(), category, stat.st_mtime, stat.st_size, now, document_id
        ))
    else:
        cur.execute("""
            INSERT INTO documents (title, path, file_type, category, file_mtime, file_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title, str(path), path.suffix.lower(), category, stat.st_mtime, stat.st_size, now
        ))
        document_id = cur.lastrowid

    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)

    for idx, chunk in enumerate(chunks):
        cur.execute("""
            INSERT INTO chunks (document_id, chunk_index, content, source_info)
            VALUES (?, ?, ?, ?)
        """, (document_id, idx, chunk, ""))

        chunk_id = cur.lastrowid
        cur.execute("""
            INSERT INTO chunks_fts (content, chunk_id, document_id)
            VALUES (?, ?, ?)
        """, (chunk, chunk_id, document_id))

    conn.commit()
    print(f"[INGESTED] {path} chunks={len(chunks)}")


def remove_deleted_files(conn, existing_paths: set):
    cur = conn.cursor()
    cur.execute("SELECT id, path FROM documents")
    rows = cur.fetchall()

    for row in rows:
        doc_id, path = row
        if path not in existing_paths:
            cur.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM chunks_fts WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            print(f"[REMOVED] {path}")

    conn.commit()


def run_ingest(full: bool = False):
    init_db()

    raw_dir = Path(settings.raw_dir)
    conn = get_conn()

    files = []
    for path in raw_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in [".txt", ".pdf", ".docx", ".doc"]:
            files.append(path)

    existing_paths = {str(p) for p in files}

    if full:
        cur = conn.cursor()
        cur.execute("DELETE FROM chunks")
        cur.execute("DELETE FROM chunks_fts")
        cur.execute("DELETE FROM documents")
        conn.commit()
        print("[FULL REINDEX] cleared database")

    for path in files:
        ingest_one(conn, path, raw_dir)

    remove_deleted_files(conn, existing_paths)
    conn.close()


if __name__ == "__main__":
    run_ingest(full=False)
