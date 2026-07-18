"""Rasterize PDF pages before sending them through the configured OCR engine."""

from __future__ import annotations

from io import BytesIO

import pypdfium2 as pdfium


class PdfRasterizationError(ValueError):
    pass


def rasterize_pdf(
    content: bytes, *, max_pages: int = 10, scale: float = 2.0
) -> list[bytes]:
    """Return one JPEG per page, bounded to protect OCR cost and memory."""
    if not content.startswith(b"%PDF-"):
        raise PdfRasterizationError("File is not a valid PDF")
    try:
        document = pdfium.PdfDocument(content)
    except Exception as exc:
        raise PdfRasterizationError("PDF could not be opened") from exc
    if len(document) == 0:
        raise PdfRasterizationError("PDF has no pages")
    if len(document) > max_pages:
        raise PdfRasterizationError(f"PDF exceeds the {max_pages}-page OCR limit")

    images: list[bytes] = []
    try:
        for page in document:
            rendered = page.render(scale=scale).to_pil().convert("RGB")
            output = BytesIO()
            rendered.save(output, format="JPEG", quality=92, optimize=True)
            images.append(output.getvalue())
    except Exception as exc:
        raise PdfRasterizationError("PDF page rasterization failed") from exc
    finally:
        document.close()
    return images
