# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic==2.9.2", "typer==0.29.2"]
# ///
# How to run: .venv/Scripts/python.exe -m evaluation.prepare_demo --output-directory data/f00-demo
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Annotated, Final

import typer

from evaluation.artifacts import sha256
from evaluation.database import snapshot_database
from evaluation.models import Category, Query, Ranking, load_queries

SQL: Final = """
CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT, path TEXT, category TEXT);
CREATE TABLE chunks(id INTEGER PRIMARY KEY, document_id INTEGER, chunk_index INTEGER, content TEXT);
CREATE VIRTUAL TABLE chunks_fts USING fts5(content, chunk_id UNINDEXED, document_id UNINDEXED);
INSERT INTO documents VALUES(1, 'synthetic manual', 'synthetic.txt', 'synthetic');
"""
CONTENTS: Final = ("Q7-42 servo adjust", "Q7-42 servo table 220V", "伺服 参数 调整", "MODEL-A current 2A", "MODEL-B current 5A")


def prepare_demo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    database = directory / "demo.db"
    with closing(sqlite3.connect(database)) as conn:
        conn.executescript(SQL)
        for index, content in enumerate(CONTENTS, 1):
            conn.execute("INSERT INTO chunks VALUES(?,1,?,?)", (index, index - 1, content))
            conn.execute("INSERT INTO chunks_fts VALUES(?,?,1)", (content, index))
        conn.commit()
    with snapshot_database(database) as copied:
        corpus = sha256(copied)
    examples: tuple[tuple[str, str, Category, tuple[int, ...]], ...] = (
        ("p", "Q7-42", "parameter", (1, 2)), ("c", "伺服", "chinese", (3,)),
        ("t", "220V", "table", (2,)), ("m", "MODEL-A", "similar_model", (4,)),
        ("n", "absent-xyz", "no_answer", ()),
    )
    queries = [Query(query_id=identifier, query=text, category=category, split="dev", origin="synthetic",
                     corpus_id=corpus, answerable=bool(relevant), relevant_chunk_ids=relevant, label_status="complete")
               for identifier, text, category, relevant in examples]
    queries.append(queries[0].model_copy(update={"query_id": "held-p", "split": "holdout"}))
    query_path = directory / "queries.jsonl"
    query_path.write_text("\n".join(q.model_dump_json() for q in queries) + "\n", encoding="utf-8")
    dataset = load_queries(query_path)
    for variant in ("good", "bad"):
        ranks = [Ranking(query_id=q.query_id, corpus_id=corpus, query_set_sha256=dataset.sha256,
                         ranked_chunk_ids=q.relevant_chunk_ids if variant == "good" else (999,), status="ok")
                 for q in queries if q.split == "dev"]
        (directory / f"{variant}.jsonl").write_text("\n".join(r.model_dump_json() for r in ranks) + "\n", encoding="utf-8")


def main(output_directory: Annotated[Path, typer.Option()]) -> None:
    try:
        prepare_demo(output_directory)
    except (OSError, sqlite3.Error) as error:
        typer.echo(f"ERROR {type(error).__name__}", err=True)
        raise typer.Exit(2) from None
    typer.echo("synthetic fixture prepared")


if __name__ == "__main__":
    typer.run(main)
