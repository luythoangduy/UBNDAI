"""Fast, non-persistent format checks for document photos before OCR.

This deliberately assesses capture quality only.  It never claims that a
document is legally valid or that its contents are correct.
"""

from __future__ import annotations

import io
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from src.models import ImageFormatCheck, ImageFormatReview, ImageLayoutFinding
from src.services.ocr.preprocessing import _find_document_quad

_MIN_SHARPNESS = 45.0
_DARK_MEAN = 55.0
_BRIGHT_MEAN = 235.0


def review_document_image(content: bytes, media_type: str) -> ImageFormatReview:
    """Return actionable capture-quality guidance without storing the upload."""
    try:
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Không thể đọc ảnh. Hãy dùng ảnh JPEG hoặc PNG hợp lệ.") from exc

    width, height = image.size
    rgb = np.asarray(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    checks: list[ImageFormatCheck] = [
        ImageFormatCheck(
            code="supported_image",
            status="pass",
            message="Ảnh JPEG/PNG hợp lệ; có thể dùng để rà soát và nhận dạng.",
        )
    ]
    layout_findings: list[ImageLayoutFinding] = []
    document_quad = _find_document_quad(bgr)
    if document_quad is None:
        layout_findings.append(
            ImageLayoutFinding(
                code="document_boundary_unclear",
                status="warning",
                message="Không xác định rõ bốn mép giấy tờ; hãy đặt giấy trên nền tương phản và chụp trọn trang.",
            )
        )
    else:
        x, y, box_width, box_height = cv2.boundingRect(document_quad)
        normalized_box = [x / width, y / height, box_width / width, box_height / height]
        edge_margin = min(
            x / width,
            y / height,
            (width - x - box_width) / width,
            (height - y - box_height) / height,
        )
        if edge_margin < 0.015:
            layout_findings.append(
                ImageLayoutFinding(
                    code="document_edge_cropped",
                    status="warning",
                    message="Giấy tờ sát mép khung hình, có nguy cơ bị cắt mất nội dung. Hãy chụp chừa viền quanh toàn bộ giấy.",
                    bounding_box=normalized_box,
                )
            )

    if sharpness < _MIN_SHARPNESS:
        checks.append(
            ImageFormatCheck(
                code="blur_risk",
                status="warning",
                message="Ảnh có dấu hiệu mờ. Giữ máy cố định và lấy nét vào phần chữ trước khi tải lên.",
            )
        )
    else:
        checks.append(ImageFormatCheck(code="sharpness_ok", status="pass", message="Độ nét ảnh đạt mức cơ bản."))

    if brightness < _DARK_MEAN:
        checks.append(
            ImageFormatCheck(
                code="too_dark",
                status="warning",
                message="Ảnh hơi tối; hãy chụp ở nơi đủ sáng và tránh bóng đổ lên văn bản.",
            )
        )
    elif brightness > _BRIGHT_MEAN:
        checks.append(
            ImageFormatCheck(
                code="overexposed",
                status="warning",
                message="Ảnh bị sáng gắt; tránh đèn phản chiếu hoặc flash trực tiếp lên giấy.",
            )
        )
    else:
        checks.append(ImageFormatCheck(code="lighting_ok", status="pass", message="Ánh sáng và độ tương phản phù hợp."))

    # Capture/layout findings are advisory.  They must never interrupt a
    # citizen's workflow; only an explicit upload/format error is rejected by
    # the route before this function is called.
    status: Literal["ready", "needs_attention", "rejected"] = "ready"
    return ImageFormatReview(
        status=status,
        media_type=media_type,  # validated by the route before reaching this service
        width=width,
        height=height,
        file_size_bytes=len(content),
        checks=checks,
        layout_findings=layout_findings,
    )
