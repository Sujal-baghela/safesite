"""
Utility functions for the CV pipeline.

Covers: image encoding, cropping violation regions, frame resizing,
and converting between OpenCV and PIL formats.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from ml.inference.detector import Detection


def encode_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
    """Encode a BGR numpy array as JPEG bytes."""
    _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def encode_png(image: np.ndarray) -> bytes:
    """Encode a BGR numpy array as PNG bytes (lossless)."""
    _, buf = cv2.imencode(".png", image)
    return buf.tobytes()


def decode_image_bytes(data: bytes) -> np.ndarray | None:
    """
    Decode raw image bytes (JPEG/PNG) to a BGR numpy array.
    Returns None if decoding fails.
    """
    nparr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img  # None on failure


def crop_detection(image: np.ndarray, detection: Detection, padding: int = 10) -> np.ndarray:
    """
    Crop the bounding box region of a detection from an image,
    with optional padding around the box.

    Args:
        image: Full BGR frame.
        detection: Detection object with bbox (x1, y1, x2, y2).
        padding: Extra pixels to include around the bbox.

    Returns:
        Cropped BGR sub-image.
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = detection.bbox
    x1 = max(0, int(x1) - padding)
    y1 = max(0, int(y1) - padding)
    x2 = min(w, int(x2) + padding)
    y2 = min(h, int(y2) + padding)
    return image[y1:y2, x1:x2]


def resize_for_inference(
    image: np.ndarray,
    target_size: int = 640,
) -> tuple[np.ndarray, float]:
    """
    Resize an image to fit within target_size × target_size while preserving
    aspect ratio. YOLO expects 640×640 by default.

    Returns:
        Tuple of (resized_image, scale_factor) for reversing coordinates.
    """
    h, w = image.shape[:2]
    scale = min(target_size / h, target_size / w)
    if scale >= 1.0:
        return image, 1.0
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    return resized, scale


def letterbox(
    image: np.ndarray,
    target_size: int = 640,
    fill_color: tuple[int, int, int] = (114, 114, 114),
) -> np.ndarray:
    """
    Resize and pad image to exact target_size × target_size using letterbox
    padding (grey bars). This is what YOLO expects for best accuracy.
    """
    resized, scale = resize_for_inference(image, target_size)
    h, w = resized.shape[:2]
    canvas = np.full((target_size, target_size, 3), fill_color, dtype=np.uint8)
    pad_top = (target_size - h) // 2
    pad_left = (target_size - w) // 2
    canvas[pad_top: pad_top + h, pad_left: pad_left + w] = resized
    return canvas
