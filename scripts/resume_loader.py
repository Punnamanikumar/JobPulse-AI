"""
Resume Loader — supports PDF, DOCX, TXT, and MD resume files.

Auto-detects the resume file in the resume/ directory.
Supports: .txt, .md, .pdf (via PyPDF2), .docx (via python-docx)

Usage:
    from resume_loader import load_resume
    text = load_resume()  # auto-detects resume file
    text = load_resume("/path/to/resume.pdf")  # explicit path
"""

from __future__ import annotations

import os
from pathlib import Path


def load_resume(path: str = "") -> str:
    """Load resume text from the given path or auto-detect from resume/ dir.

    Supported formats: .txt, .md, .pdf, .docx, .doc

    Args:
        path: Explicit path to resume file. If empty, auto-detects from config.

    Returns:
        Resume text content as a string.

    Raises:
        FileNotFoundError: If no resume file is found.
        ValueError: If resume content is too short (<50 chars).
    """
    if not path:
        from config import get_config
        path = get_config().resume_path

    if not path:
        raise FileNotFoundError(
            "No resume file found!\n"
            "Please add your resume to the resume/ directory.\n"
            "Supported formats: .pdf, .docx, .txt, .md\n"
            "See resume/sample_profile.txt for the expected format."
        )

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Resume file not found: {path}")

    ext = file_path.suffix.lower()

    if ext in (".txt", ".md"):
        text = _load_text(file_path)
    elif ext == ".pdf":
        text = _load_pdf(file_path)
    elif ext in (".docx", ".doc"):
        text = _load_docx(file_path)
    else:
        # Try reading as plain text
        text = _load_text(file_path)

    text = text.strip()

    if len(text) < 50:
        raise ValueError(
            f"Resume file '{file_path.name}' is too short ({len(text)} chars).\n"
            "Please fill in your complete details.\n"
            "See resume/sample_profile.txt for the expected format."
        )

    return text


def _load_text(path: Path) -> str:
    """Load a plain text file."""
    return path.read_text(encoding="utf-8")


def _load_pdf(path: Path) -> str:
    """Load text from a PDF file using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ImportError(
            "PyPDF2 is required to read PDF resumes.\n"
            "Install it with: pip install PyPDF2>=3.0.0"
        )

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    if not pages:
        raise ValueError(
            f"Could not extract text from PDF: {path.name}\n"
            "The PDF may be image-based. Please use a text-based PDF, "
            "or convert your resume to .txt or .docx format."
        )

    return "\n\n".join(pages)


def _load_docx(path: Path) -> str:
    """Load text from a DOCX file using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is required to read DOCX resumes.\n"
            "Install it with: pip install python-docx>=1.0.0"
        )

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def get_resume_info() -> dict:
    """Get metadata about the loaded resume (for logging/display).

    Returns:
        dict with keys: path, format, size_chars, name
    """
    from config import get_config
    cfg = get_config()

    if not cfg.resume_path:
        return {"path": "", "format": "none", "size_chars": 0, "name": ""}

    path = Path(cfg.resume_path)
    try:
        text = load_resume(cfg.resume_path)
        return {
            "path": cfg.resume_path,
            "format": path.suffix.lower().lstrip("."),
            "size_chars": len(text),
            "name": path.name,
        }
    except Exception:
        return {
            "path": cfg.resume_path,
            "format": path.suffix.lower().lstrip("."),
            "size_chars": 0,
            "name": path.name,
        }
