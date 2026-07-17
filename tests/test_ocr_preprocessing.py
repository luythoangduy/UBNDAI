import cv2
import numpy as np

from src.services.ocr.preprocessing import (
    _estimate_skew_angle,
    preprocess_document_image,
)


def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _decode(content: bytes) -> np.ndarray:
    array = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    assert image is not None
    return image


def _tilted_page_on_dark_background() -> bytes:
    """A bright page photographed at an angle against a dark table."""
    canvas = np.full((900, 1200, 3), 30, dtype=np.uint8)
    quad = np.array([[260, 120], [950, 180], [900, 760], [210, 700]], dtype=np.int32)
    cv2.fillConvexPoly(canvas, quad, (235, 235, 235))
    for y in range(220, 640, 60):
        cv2.line(canvas, (320, y), (830, y + 40), (40, 40, 40), 6)
    return _encode_png(canvas)


def _skewed_text_page() -> bytes:
    """A full-frame page with a slightly rotated text block (no visible page edges)."""
    canvas = np.full((800, 1100, 3), 250, dtype=np.uint8)
    center = (550, 400)
    matrix = cv2.getRotationMatrix2D(center, 6.0, 1.0)
    block = np.full_like(canvas, 250)
    for y in range(250, 560, 45):
        cv2.line(block, (250, y), (850, y), (20, 20, 20), 10)
    canvas = cv2.warpAffine(block, matrix, (1100, 800), borderValue=(250, 250, 250))
    return _encode_png(canvas)


def test_tilted_page_gets_perspective_corrected():
    result = preprocess_document_image(_tilted_page_on_dark_background())

    assert "perspective_correction" in result.applied_steps
    assert result.mime_type == "image/jpeg"
    corrected = _decode(result.content)
    # After warping, the output frame is the page itself: mostly bright pixels.
    assert float(cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY).mean()) > 150


def test_skewed_text_gets_deskewed():
    original = _skewed_text_page()
    result = preprocess_document_image(original)

    deskew_steps = [s for s in result.applied_steps if s.startswith("deskew_")]
    assert deskew_steps, f"expected a deskew step, got {result.applied_steps}"
    residual = abs(_estimate_skew_angle(_decode(result.content)))
    initial = abs(_estimate_skew_angle(_decode(original)))
    assert residual < initial


def test_oversized_image_is_downscaled():
    huge = np.full((3200, 2600, 3), 240, dtype=np.uint8)
    result = preprocess_document_image(_encode_png(huge))

    assert "downscale" in result.applied_steps
    corrected = _decode(result.content)
    assert max(corrected.shape[:2]) <= 2400


def test_invalid_bytes_fall_back_to_original():
    junk = b"this is not an image"
    result = preprocess_document_image(junk)

    assert result.content == junk
    assert result.mime_type == ""
    assert result.applied_steps == ["decode_failed"]


def test_contrast_enhancement_always_applied_on_valid_images():
    plain = np.full((600, 800, 3), 200, dtype=np.uint8)
    result = preprocess_document_image(_encode_png(plain))

    assert "clahe_contrast" in result.applied_steps
    assert result.mime_type == "image/jpeg"
