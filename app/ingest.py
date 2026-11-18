from pathlib import Path
from datetime import datetime
import sqlite3
import sys

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
    cur = conn.cursor()

    cur.execute("SELECT id, file_mtime, file_size FROM documents WHERE path = ?", (str(path),))
    old = cur.fetchone()

    if old and float(old[1]) == float(stat.st_mtime) and int(old[2]) == int(stat.st_size):
        print(f"[UNCHANGED] {path}", flush=True)
        return "unchanged"

    print(f"[PARSING] {path}", flush=True)
    text = extract_text(path)

    if not text.strip():
        print(f"[SKIP] no text extracted (empty, scanned, or unreadable document): {path}", flush=True)
        return "skipped"

    title = path.name
    category = file_category(path, raw_dir)
    now = datetime.utcnow().isoformat()

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
    print(f"[INGESTED] {path} chunks={len(chunks)}", flush=True)
    return "ingested"


def remove_deleted_files(conn, existing_paths: set):
    cur = conn.cursor()
    cur.execute("SELECT id, path FROM documents")
    rows = cur.fetchall()

    removed = 0
    for row in rows:
        doc_id, path = row
        if path not in existing_paths:
            cur.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM chunks_fts WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            removed += 1
            print(f"[REMOVED] {path}", flush=True)

    conn.commit()
    return removed


def run_ingest(full: bool = False):
    raw_dir = Path(settings.raw_dir)
    print(f"[START] RAW_DIR={raw_dir}", flush=True)
    print(f"[START] DB_PATH={settings.db_path}", flush=True)

    if not raw_dir.exists():
        raise FileNotFoundError(f"RAW_DIR does not exist: {raw_dir}. Check RAW_DIR in .env.")
    if not raw_dir.is_dir():
        raise NotADirectoryError(f"RAW_DIR is not a directory: {raw_dir}. Check RAW_DIR in .env.")

    print("[SCAN] Looking for .txt, .pdf, .docx, .doc files...", flush=True)
    files = []
    for path in raw_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in [".txt", ".pdf", ".docx", ".doc"]:
            files.append(path)

    files.sort()
    print(f"[SCAN] Found {len(files)} supported file(s)", flush=True)
    if not files:
        print("[WARNING] No supported files found. Check RAW_DIR and document extensions.", flush=True)

    existing_paths = {str(p) for p in files}
    counts = {"ingested": 0, "unchanged": 0, "skipped": 0}

    init_db()
    conn = get_conn()
    try:
        if full:
            cur = conn.cursor()
            cur.execute("DELETE FROM chunks")
            cur.execute("DELETE FROM chunks_fts")
            cur.execute("DELETE FROM documents")
            conn.commit()
            print("[FULL REINDEX] cleared database", flush=True)

        for path in files:
            counts[ingest_one(conn, path, raw_dir)] += 1

        counts["removed"] = remove_deleted_files(conn, existing_paths)
    finally:
        conn.close()

    summary = " ".join(f"{name}={count}" for name, count in counts.items())
    print(f"[DONE] files={len(files)} {summary}", flush=True)
    return counts


if __name__ == "__main__":
    try:
        run_ingest(full=False)
    except (OSError, sqlite3.Error) as error:
        print(f"[ERROR] {error}", file=sys.stderr, flush=True)
        sys.exit(1)
