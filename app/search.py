from app.db import get_conn


def list_documents():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, path, file_type, category, file_size, updated_at
        FROM documents
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_document(document_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, path, file_type, category, file_size, updated_at
        FROM documents
        WHERE id = ?
    """, (document_id,))
    doc = cur.fetchone()
    if not doc:
        conn.close()
        return None

    cur.execute("""
        SELECT chunk_index, content, source_info
        FROM chunks
        WHERE document_id = ?
        ORDER BY chunk_index ASC
    """, (document_id,))
    chunks = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "document": dict(doc),
        "chunks": chunks,
        "content": "\n".join(c["content"] for c in chunks)
    }


def search_documents(query: str, limit: int = 5):
    conn = get_conn()
    cur = conn.cursor()

    sql = """
    SELECT c.id AS chunk_id,
           d.id AS document_id,
           d.title,
           d.category,
           c.chunk_index,
           c.content
    FROM chunks_fts f
    JOIN chunks c ON c.id = f.chunk_id
    JOIN documents d ON d.id = c.document_id
    WHERE chunks_fts MATCH ?
    LIMIT ?
    """
    cur.execute(sql, (query, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
