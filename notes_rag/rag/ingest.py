"""Document loading and chunking."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from pypdf import PdfReader

# File extensions we know how to read.
SUPPORTED_EXTS = {".txt", ".md", ".markdown", ".pdf"}


@dataclass
class Chunk:
    """A piece of a document, ready to embed."""
    text: str
    source: str         # absolute path of the file the chunk came from
    chunk_index: int    # position of this chunk within the source file

    @property
    def id(self) -> str:
        # Stable ID based on source + chunk_index so re-ingesting doesn't dupe.
        digest = hashlib.sha1(f"{self.source}:{self.chunk_index}".encode()).hexdigest()
        return digest[:16]


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            # Skip pages we can't decode rather than blowing up the whole ingest.
            continue
    return "\n\n".join(pages)


def read_document(path: Path) -> str:
    """Return the full text of a single supported document."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext in SUPPORTED_EXTS:
        return _read_text_file(path)
    raise ValueError(f"Unsupported file type: {path}")


def iter_documents(root: Path) -> Iterator[Path]:
    """Walk a path and yield supported document files."""
    if root.is_file():
        if root.suffix.lower() in SUPPORTED_EXTS:
            yield root
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            yield p


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping chunks.

    Tries to split on paragraph then sentence boundaries before falling back
    to a hard character cut, so chunks read more naturally than a raw slice.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    # First pass: split on blank lines (paragraphs).
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= chunk_size:
            buf = f"{buf}\n\n{para}".strip() if buf else para
        else:
            if buf:
                chunks.append(buf)
            # If a single paragraph is bigger than chunk_size, hard-split it.
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i : i + chunk_size])
                buf = ""
            else:
                buf = para
    if buf:
        chunks.append(buf)

    # Add overlap by prepending the tail of the previous chunk.
    if overlap > 0 and len(chunks) > 1:
        with_overlap = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            with_overlap.append(f"{tail}\n{chunks[i]}")
        chunks = with_overlap

    return chunks


def build_chunks(paths: Iterable[Path], **chunk_kwargs) -> list[Chunk]:
    """Read every file in `paths` and return a flat list of Chunks."""
    out: list[Chunk] = []
    for path in paths:
        try:
            text = read_document(path)
        except Exception as e:
            print(f"  ! skipping {path}: {e}")
            continue
        for i, piece in enumerate(chunk_text(text, **chunk_kwargs)):
            out.append(Chunk(text=piece, source=str(path.resolve()), chunk_index=i))
    return out
