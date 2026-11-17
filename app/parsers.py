from pathlib import Path
from pypdf import PdfReader
from docx import Document
import subprocess
import fitz


def extract_text_from_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_from_pdf(path: Path) -> str:
    # 优先使用 pymupdf
    try:
        doc = fitz.open(str(path))
        texts = []
        for page in doc:
            texts.append(page.get_text("text"))
        full = "\n".join(texts).strip()
        if full:
            return full
    except Exception:
        pass

    # 回退 pypdf
    try:
        reader = PdfReader(str(path))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


def extract_text_from_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_doc(path: Path) -> str:
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            errors="ignore"
        )
        return result.stdout
    except Exception:
        return ""


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return extract_text_from_txt(path)
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix == ".doc":
        return extract_text_from_doc(path)
    return ""
