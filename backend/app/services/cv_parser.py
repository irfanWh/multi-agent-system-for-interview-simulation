"""
CV parser utilities for InterviewAI.
Supports PDF and DOCX file formats.
"""
import io
import re
from typing import Optional


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract raw text from a DOCX file."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def clean_cv_text(raw_text: str) -> str:
    """
    Clean extracted CV text:
    - Collapse multiple whitespace / newlines
    - Remove non-printable characters
    - Strip leading/trailing whitespace
    """
    # Remove non-printable chars (keep newlines and tabs temporarily)
    text = re.sub(r"[^\S\n]+", " ", raw_text)
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return text.strip()


def parse_cv(file_bytes: bytes, filename: str) -> str:
    """
    High-level parser: detect format from filename extension,
    extract text, then clean it.
    Returns cleaned CV text.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        raw = extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        raw = extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: .{ext}. Use PDF or DOCX.")

    return clean_cv_text(raw)
