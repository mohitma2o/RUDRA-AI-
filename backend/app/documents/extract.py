"""Document text extraction with user-facing validation errors."""

from pathlib import Path


class DocumentPasswordError(ValueError):
    """Raised when a PDF needs a non-empty password."""


class ScannedDocumentError(ValueError):
    """Raised when a PDF has no usable selectable text."""


def extract_document(path: Path, *, max_chars: int, max_pages: int) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    elif suffix == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except (PdfReadError, ValueError) as exc:
                raise DocumentPasswordError("This PDF is password-protected; a password is needed.") from exc
            if not unlocked:
                raise DocumentPasswordError("This PDF is password-protected; a password is needed.")
        if len(reader.pages) > max_pages:
            raise ValueError(f"The PDF exceeds the {max_pages}-page processing limit.")
        pages = [page.extract_text() or "" for page in reader.pages]
        if pages and sum(len(page.strip()) for page in pages) / len(pages) < 20:
            raise ScannedDocumentError("This PDF has no selectable text; OCR is not enabled.")
        text = "\n".join(f"[p. {index}] {page}" for index, page in enumerate(pages, start=1))
    elif suffix == ".docx":
        from docx import Document

        document = Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        parts.extend(
            " | ".join(cell.text for cell in row.cells)
            for table in document.tables
            for row in table.rows
        )
        text = "\n".join(parts)
    elif suffix == ".pptx":
        from pptx import Presentation

        presentation = Presentation(str(path))
        text = "\n".join(
            shape.text
            for slide in presentation.slides
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False) and shape.text.strip()
        )
    else:
        raise ValueError(f"Unsupported document type: {suffix or '(no extension)'}")

    text = text.strip()
    if not text:
        raise ValueError("No readable text was found in the document.")
    if len(text) > max_chars:
        raise ValueError(f"Document text exceeds the {max_chars:,} character processing limit.")
    return text
