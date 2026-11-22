from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path
from typing import Final
from xml.etree import ElementTree

import fitz

from evaluation.artifacts import Provenance, provenance, sha256
from evaluation.database import DatabaseSnapshot, describe_database, snapshot_database
from evaluation.models import EvaluationError, FrozenModel

IMAGE_SUFFIXES: Final = frozenset((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"))
VIDEO_SUFFIXES: Final = frozenset((".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"))


class FileMetadata(FrozenModel):
    file_id: str
    suffix: str
    bytes: int | None = None
    sha256: str | None = None
    status: str
    reason: str | None = None
    pages: int | None = None
    text_sparse_pages: int | None = None
    text_sparse_ratio: float | None = None
    extracted_nonwhitespace_characters: int | None = None
    image_reference_occurrences: int | None = None
    pages_with_image_references: int | None = None
    paragraphs: int | None = None
    tables: int | None = None
    media_entries: int | None = None
    utf8_decodable: bool | None = None
    duration_hours: float | None = None


class Inventory(FrozenModel):
    kind: str = "inventory"
    provenance: Provenance
    status: str
    file_count: int
    total_bytes: int
    total_bytes_scope: str = "sum_known_sizes;unknown_sizes_excluded"
    known_size_file_count: int
    unknown_size_file_count: int
    skipped_links: int
    standalone_image_files: int
    video_files: int
    video_duration_hours: float | None = None
    video_duration_reason: str = "duration_probe_not_implemented"
    scan_measure: str = "text_sparse_lt20_nonwhitespace_characters;not_confirmed_scanning"
    image_measure: str = "per_page_image_references;may_repeat_or_be_unused"
    future_raw_bytes: str = "approximately_20GB_user_R01;GB_or_GiB_not_frozen"
    daily_increment: str = "negligible_user_R01"
    budget: str = "unknown"
    files: tuple[FileMetadata, ...]
    database: DatabaseSnapshot | None


def _is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _scan_error(error: OSError) -> None:
    raise EvaluationError("directory_scan_failed") from error


def inventory(root: Path, database: Path | None) -> Inventory:
    if not root.is_dir() or _is_link(root):
        raise EvaluationError("root_missing_not_directory_or_link")
    paths: list[Path] = []
    skipped = 0
    for base, directories, filenames in os.walk(root, followlinks=False, onerror=_scan_error):
        for name in tuple(directories):
            if _is_link(Path(base) / name):
                directories.remove(name)
                skipped += 1
        for name in filenames:
            path = Path(base) / name
            if _is_link(path):
                skipped += 1
            elif name != ".gitkeep":
                paths.append(path)
    files = tuple(_file_metadata(path, f"file-{index:04d}") for index, path in enumerate(sorted(paths), 1))
    description: DatabaseSnapshot | None = None
    if database is not None:
        with snapshot_database(database) as copied:
            description = describe_database(copied)
    return Inventory(provenance=provenance(), status="complete" if all(f.status == "ok" for f in files) else "partial",
                     file_count=len(files), total_bytes=sum(f.bytes for f in files if f.bytes is not None),
                     known_size_file_count=sum(f.bytes is not None for f in files),
                     unknown_size_file_count=sum(f.bytes is None for f in files), skipped_links=skipped,
                     standalone_image_files=sum(f.suffix in IMAGE_SUFFIXES for f in files),
                     video_files=sum(f.suffix in VIDEO_SUFFIXES for f in files), files=files, database=description)


def _file_metadata(path: Path, alias: str) -> FileMetadata:
    suffix = path.suffix.lower()
    try:
        before = path.stat()
    except OSError as error:
        return FileMetadata(file_id=alias, suffix=suffix, status="error", reason=type(error).__name__)
    try:
        digest = sha256(path)
    except OSError as error:
        return FileMetadata(file_id=alias, suffix=suffix, bytes=before.st_size, status="error", reason=type(error).__name__)
    try:
        result = _structure(path, alias)
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError, fitz.FileDataError, RuntimeError) as error:
        result = FileMetadata(file_id=alias, suffix=suffix, status="error", reason=type(error).__name__)
    try:
        after = path.stat()
    except OSError:
        return result.model_copy(update={"bytes": before.st_size, "sha256": None, "status": "unstable", "reason": "post_read_stat_failed"})
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return result.model_copy(update={"bytes": before.st_size, "sha256": None, "status": "unstable", "reason": "size_or_mtime_changed"})
    return result.model_copy(update={"bytes": before.st_size, "sha256": digest})


def _structure(path: Path, alias: str) -> FileMetadata:
    base = FileMetadata(file_id=alias, suffix=path.suffix.lower(), status="ok")
    if path.suffix.lower() == ".pdf":
        with fitz.open(path) as pdf:
            if pdf.needs_pass:
                return base.model_copy(update={"status": "encrypted", "reason": "password_required"})
            chars = [len("".join(page.get_text("text").split())) for page in pdf]
            images = [len(page.get_images(full=True)) for page in pdf]
            return base.model_copy(update={"pages": len(pdf), "text_sparse_pages": sum(n < 20 for n in chars),
                "text_sparse_ratio": sum(n < 20 for n in chars) / len(pdf) if len(pdf) else None,
                "extracted_nonwhitespace_characters": sum(chars), "image_reference_occurrences": sum(images),
                "pages_with_image_references": sum(n > 0 for n in images)})
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as archive:
            document = ElementTree.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            return base.model_copy(update={"paragraphs": len(document.findall(".//w:p", ns)),
                "tables": len(document.findall(".//w:tbl", ns)),
                "media_entries": sum(n.startswith("word/media/") and not n.endswith("/") for n in archive.namelist()),
                "reason": "docx_pages_unavailable_without_layout"})
    if path.suffix.lower() == ".txt":
        try:
            with path.open("r", encoding="utf-8") as stream:
                for _line in stream:
                    pass
        except UnicodeDecodeError:
            return base.model_copy(update={"status": "partial", "utf8_decodable": False, "reason": "invalid_utf8"})
        return base.model_copy(update={"utf8_decodable": True})
    if path.suffix.lower() in IMAGE_SUFFIXES:
        return base.model_copy(update={"reason": "image_content_not_probed"})
    if path.suffix.lower() in VIDEO_SUFFIXES:
        return base.model_copy(update={"status": "partial", "reason": "duration_probe_not_implemented"})
    return base.model_copy(update={"status": "unsupported", "reason": "structure_probe_not_implemented"})
