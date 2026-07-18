from src.models import UploadIntentRequest
from src.services.ocr.pdf import rasterize_pdf


def _one_page_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 36 >>\nstream\nBT /F1 12 Tf 20 100 Td (OCR) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, item in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode())
        content.extend(item + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(content)


def test_pdf_upload_contract_and_rasterization():
    request = UploadIntentRequest(
        filename="official-form.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )
    pages = rasterize_pdf(_one_page_pdf())

    assert request.content_type == "application/pdf"
    assert len(pages) == 1
    assert pages[0].startswith(b"\xff\xd8\xff")
