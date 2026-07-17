"""Image preprocessing for handwriting OCR: flatten & front-align document photos.

Citizens photograph paper forms at an angle, rotated, in poor lighting. Before
the image reaches the vision LLM this module:

1. Applies EXIF orientation (phones store rotation as metadata).
2. Detects the document's quadrilateral and warps it to a frontal, rectangular
   view (perspective correction — "chính diện").
3. Falls back to skew-angle rotation ("làm phẳng") when no clean quad is found.
4. Boosts local contrast with CLAHE so faint pencil/ink survives JPEG.

Every step degrades gracefully: on any failure the original bytes are returned
untouched — preprocessing must never break OCR.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSION_PX = 2400
# A candidate page contour must cover at least this share of the frame.
MIN_QUAD_AREA_RATIO = 0.25
# Deskew only meaningful tilts; near-zero angles are noise, large ones are
# usually landscape shots, not skew.
DESKEW_MIN_ANGLE = 0.5
DESKEW_MAX_ANGLE = 15.0
JPEG_QUALITY = 92
# Snapshots chỉ phục vụ hiển thị từng bước trên FE — nén nhỏ để payload nhẹ.
SNAPSHOT_MAX_DIMENSION_PX = 1200
SNAPSHOT_JPEG_QUALITY = 80


@dataclass(frozen=True)
class StepSnapshot:
    """Ảnh chụp sau một bước tiền xử lý, dùng cho FE minh hoạ pipeline."""

    name: str
    content: bytes
    mime_type: str = "image/jpeg"


@dataclass(frozen=True)
class PreprocessedImage:
    content: bytes
    mime_type: str
    applied_steps: list[str] = field(default_factory=list)
    step_snapshots: list[StepSnapshot] = field(default_factory=list)


def _decode(image_bytes: bytes) -> np.ndarray:
    """Decode via PIL (handles EXIF rotation) into an OpenCV BGR array."""
    with Image.open(io.BytesIO(image_bytes)) as pil_image:
        transposed = ImageOps.exif_transpose(pil_image)
        rgb = transposed.convert("RGB")
        return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)


def _downscale(image: np.ndarray) -> tuple[np.ndarray, bool]:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= MAX_DIMENSION_PX:
        return image, False
    scale = MAX_DIMENSION_PX / longest
    resized = cv2.resize(
        image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA
    )
    return resized, True


def _order_quad(points: np.ndarray) -> np.ndarray:
    """Order 4 corner points as top-left, top-right, bottom-right, bottom-left."""
    pts = points.reshape(4, 2).astype(np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).ravel()
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    return ordered


def _find_document_quad(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median = float(np.median(blurred))
    lower = int(max(0, 0.66 * median))
    upper = int(min(255, 1.33 * median))
    edges = cv2.Canny(blurred, lower, upper)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = image.shape[0] * image.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < frame_area * MIN_QUAD_AREA_RATIO:
            break
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx
    return None


def _warp_to_frontal(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    ordered = _order_quad(quad)
    tl, tr, br, bl = ordered
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 50 or height < 50:
        return image
    target = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(ordered, target)
    return cv2.warpPerspective(image, matrix, (width, height))


def _estimate_skew_angle(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # np.where yields (row, col); minAreaRect expects (x, y) points.
    coords = np.column_stack(np.where(thresholded > 0)[::-1])
    if len(coords) < 100:
        return 0.0
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    # Normalize OpenCV's rect angle into (-45, 45]: rotating by the result
    # (counterclockwise-positive) cancels the measured skew.
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90
    return float(angle)


def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _enhance_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    merged = cv2.merge((clahe.apply(lightness), a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def _encode_snapshot(image: np.ndarray, name: str) -> StepSnapshot | None:
    """Encode a preview-sized JPEG of the current stage; None on encode failure."""
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest > SNAPSHOT_MAX_DIMENSION_PX:
        scale = SNAPSHOT_MAX_DIMENSION_PX / longest
        image = cv2.resize(
            image,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(
        ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_JPEG_QUALITY]
    )
    if not ok:
        return None
    return StepSnapshot(name=name, content=encoded.tobytes())


def preprocess_document_image(
    image_bytes: bytes, *, capture_steps: bool = False
) -> PreprocessedImage:
    """Flatten and front-align a document photo. Never raises: falls back to the
    original bytes on any decoding/processing failure.

    ``capture_steps=True`` additionally records a preview JPEG after each visual
    stage (original/EXIF → perspective|deskew → CLAHE) for the FE step viewer.
    """
    steps: list[str] = []
    snapshots: list[StepSnapshot] = []

    def snap(image: np.ndarray, name: str) -> None:
        if not capture_steps:
            return
        snapshot = _encode_snapshot(image, name)
        if snapshot is not None:
            snapshots.append(snapshot)

    try:
        image = _decode(image_bytes)
        steps.append("exif_orientation")
    except Exception:
        logger.warning("Image preprocessing skipped: decode failed", exc_info=True)
        return PreprocessedImage(
            content=image_bytes, mime_type="", applied_steps=["decode_failed"]
        )

    try:
        image, downscaled = _downscale(image)
        if downscaled:
            steps.append("downscale")
        snap(image, "original")

        quad = _find_document_quad(image)
        if quad is not None:
            warped = _warp_to_frontal(image, quad)
            if warped is not image:
                image = warped
                steps.append("perspective_correction")
                snap(image, "perspective_correction")
        else:
            angle = _estimate_skew_angle(image)
            if DESKEW_MIN_ANGLE <= abs(angle) <= DESKEW_MAX_ANGLE:
                image = _rotate(image, angle)
                steps.append(f"deskew_{angle:.1f}deg")
                snap(image, "deskew")

        image = _enhance_contrast(image)
        steps.append("clahe_contrast")
        snap(image, "clahe_contrast")

        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            raise ValueError("JPEG encoding failed")
        return PreprocessedImage(
            content=encoded.tobytes(),
            mime_type="image/jpeg",
            applied_steps=steps,
            step_snapshots=snapshots,
        )
    except Exception:
        logger.warning("Image preprocessing failed; using original image", exc_info=True)
        return PreprocessedImage(
            content=image_bytes, mime_type="", applied_steps=["preprocess_failed"]
        )
