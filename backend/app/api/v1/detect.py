"""
Detection endpoints.

POST /api/v1/detect/image  — sync: upload image → YOLO inference → save violation
POST /api/v1/detect/video  — async: upload video → enqueue ARQ job → return job_id

File validation:
  - Extension whitelist (jpg, jpeg, png, mp4, mov, avi)
  - Magic-bytes check (Phase 5 adds full magic-bytes lib; here we check header bytes)
  - 50 MB max for images, 500 MB for video
"""

import io
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.storage import upload_snapshot
from app.crud.violation import create_violation
from app.models.user import User
from app.schemas.violation import ImageInferenceResponse, VideoProcessResponse
from app.tasks.worker import enqueue_video_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detect", tags=["detection"])

# ---------------------------------------------------------------------------
# File validation helpers
# ---------------------------------------------------------------------------

IMAGE_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG":      "image/png",
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

MAX_IMAGE_BYTES = 50 * 1024 * 1024    # 50 MB
MAX_VIDEO_BYTES = 500 * 1024 * 1024   # 500 MB


def _check_image_magic(header: bytes) -> str:
    """
    Verify image magic bytes and return content-type.
    Raises 400 if the file header does not match a known image format.
    """
    for magic, content_type in IMAGE_MAGIC.items():
        if header.startswith(magic):
            return content_type
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="File is not a valid JPEG or PNG image (magic bytes mismatch)",
    )


def _check_video_extension(filename: str) -> None:
    """Raise 400 if the file extension is not in the allowed video set."""
    from pathlib import Path
    ext = Path(filename).suffix.lower()
    if ext not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video format. Allowed: {', '.join(VIDEO_EXTENSIONS)}",
        )


# ---------------------------------------------------------------------------
# Detector singleton — loaded at first request, reused thereafter
# ---------------------------------------------------------------------------

_detector = None


def get_detector():
    """
    Lazy-load the PPE detector singleton.
    Returns None (and logs a warning) if model weights are missing,
    so the endpoint still runs and returns a graceful error.
    """
    global _detector
    if _detector is not None:
        return _detector

    from pathlib import Path

    model_path = Path("ml/models/ppe_yolo11.pt")
    if not model_path.exists():
        logger.warning(
            "YOLO model not found at %s — inference disabled. "
            "Download weights from Roboflow Construction Safety dataset.",
            model_path,
        )
        return None

    from ml.inference.detector import PPEDetector
    _detector = PPEDetector(model_path)
    _detector.load()
    return _detector


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/image",
    response_model=ImageInferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload an image, run PPE detection, save any violation",
)
async def detect_image(
    file: Annotated[UploadFile, File(description="JPEG or PNG image, max 50 MB")],
    site_id: Annotated[str, Form(description="Site this image is from")],
    camera_id: Annotated[str | None, Form()] = None,
    save_violation: Annotated[bool, Form()] = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImageInferenceResponse:
    """
    Full pipeline in one request:
    1. Validate file (extension + magic bytes)
    2. Run YOLO11 inference
    3. If violation detected: upload snapshot to R2, insert DB record
    4. Return detections + violation ID + signed snapshot URL
    """
    import numpy as np
    import cv2

    # --- Validation ---
    if file.size and file.size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 50 MB limit")

    image_bytes = await file.read()
    _check_image_magic(image_bytes[:8])

    # --- Decode image ---
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not decode image — file may be corrupt",
        )

    # --- Inference ---
    detector = get_detector()
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detection model not loaded. Contact administrator.",
        )

    result = detector.predict(img)

    # --- Save violation if detected ---
    violation_id: str | None = None
    snapshot_url: str | None = None

    if result.has_violation and save_violation:
        # Encode annotated frame as JPEG for the snapshot
        annotated = detector.annotate_frame(img, result)
        _, jpeg_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        snapshot_bytes = jpeg_buf.tobytes()

        snapshot_key, _ = await upload_snapshot(
            snapshot_bytes,
            site_id=site_id,
            camera_id=camera_id,
        )

        from app.core.storage import get_signed_url
        snapshot_url = await get_signed_url(snapshot_key) if snapshot_key else None

        violation = await create_violation(
            db,
            site_id=site_id,
            camera_id=camera_id,
            violation_type=result.primary_violation_type,
            confidence_score=result.max_confidence,
            snapshot_key=snapshot_key or None,
            snapshot_url=snapshot_url,
        )
        violation_id = violation.id
        logger.info(
            "Violation saved: id=%s type=%s site=%s conf=%.2f",
            violation_id, result.primary_violation_type, site_id, result.max_confidence,
        )

    from app.schemas.violation import DetectionItem
    return ImageInferenceResponse(
        has_violation=result.has_violation,
        violation_types=result.violation_types,
        primary_violation_type=result.primary_violation_type,
        max_confidence=result.max_confidence,
        detections=[DetectionItem(**d.to_dict()) for d in result.detections],
        inference_ms=result.inference_ms,
        violation_id=violation_id,
        snapshot_url=snapshot_url,
    )


@router.post(
    "/video",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a video for async PPE detection (returns job ID)",
)
async def detect_video(
    file: Annotated[UploadFile, File(description="Video file, max 500 MB")],
    site_id: Annotated[str, Form()],
    camera_id: Annotated[str | None, Form()] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoProcessResponse:
    """
    Non-blocking video processing:
    1. Validate extension
    2. Upload raw video to R2
    3. Enqueue ARQ background task
    4. Return job_id — client polls GET /jobs/{job_id} for status
    """
    if file.size and file.size > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Video exceeds 500 MB limit")

    _check_video_extension(file.filename or "video.mp4")

    video_bytes = await file.read()

    # Upload raw video to R2 first
    from pathlib import Path
    ext = Path(file.filename or "video.mp4").suffix.lstrip(".")
    video_key, _ = await upload_snapshot(
        video_bytes,
        site_id=site_id,
        camera_id=camera_id,
        content_type=f"video/{ext}",
    )

    # Enqueue background processing job
    job_id = await enqueue_video_job(
        video_key=video_key,
        site_id=site_id,
        camera_id=camera_id,
    )

    return VideoProcessResponse(
        job_id=job_id,
        status="queued",
        message="Video queued for processing. Poll /jobs/{job_id} for status.",
    )
