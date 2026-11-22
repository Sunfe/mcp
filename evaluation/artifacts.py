from __future__ import annotations

import hashlib
import importlib.metadata
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from evaluation.models import EvaluationError, FrozenModel
from evaluation.resources import Hardware, hardware

PROJECT: Final = Path(__file__).resolve().parent.parent


class Provenance(FrozenModel):
    schema_version: str = "f00-1"
    tool_version: str = "f00-1-r1-r2"
    collected_at_utc: str
    python: str
    sqlite: str
    dependencies: dict[str, str]
    sources_sha256: dict[str, str]
    hardware: Hardware


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def provenance() -> Provenance:
    import sqlite3

    sources = sorted((PROJECT / "evaluation").glob("*.py"))
    sources.extend(PROJECT / "app" / name for name in ("search.py", "db.py", "config.py"))
    return Provenance(
        collected_at_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
        sqlite=sqlite3.sqlite_version,
        dependencies={name: importlib.metadata.version(name) for name in ("pydantic", "typer", "PyMuPDF")},
        sources_sha256={path.relative_to(PROJECT).as_posix(): sha256(path) for path in sources},
        hardware=hardware(),
    )


def ensure_new_output(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise EvaluationError("output_already_exists")


def write_report(report: BaseModel, path: Path) -> None:
    ensure_new_output(path)
    encoded = report.model_dump_json(indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
