from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.artifacts import sha256
from evaluation.models import EvaluationError, FrozenModel


class DatabaseSnapshot(FrozenModel):
    corpus_id: str
    bytes: int
    documents: int
    chunks: int
    fts_rows: int
    quick_check: str


def readonly_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def describe_database(path: Path) -> DatabaseSnapshot:
    with closing(readonly_connection(path)) as conn:
        counts = [int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                  for table in ("documents", "chunks", "chunks_fts")]
        checks = [str(row[0]) for row in conn.execute("PRAGMA quick_check")]
    if checks != ["ok"]:
        raise EvaluationError("database_integrity_failed")
    return DatabaseSnapshot(corpus_id=sha256(path), bytes=path.stat().st_size,
                            documents=counts[0], chunks=counts[1], fts_rows=counts[2], quick_check="ok")


@contextmanager
def snapshot_database(source: Path) -> Iterator[Path]:
    """Backup reads WAL consistently; no schema or index is created on source."""
    if not source.is_file():
        raise EvaluationError("database_missing_or_not_file")
    with TemporaryDirectory(prefix="f00-snapshot-") as temporary:
        target = Path(temporary) / "snapshot.db"
        with closing(readonly_connection(source)) as original, closing(sqlite3.connect(target)) as copied:
            original.backup(copied)
        yield target
