"""
ARQ worker configuration and background task registry.

Tasks:
  - process_video_task: download video from R2, extract frames,
    run YOLO11 batch inference, save violations to DB, send alerts.

Worker is started via:
    arq app.tasks.worker.WorkerSettings
"""

import logging
import tempfile
import uuid
from pathlib import Path

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def process_video_task(
    ctx: dict,
    *,
    video_key: str,
    site_id: str,
    camera_id: str | None,
    job_id: str,
) -> dict:
    """
    Full async video processing pipeline:
      1. Download video from R2 to a temp file
      2. Run VideoProcessor (frame extraction + YOLO batch inference)
      3. For each violation frame: upload snapshot to R2, insert DB record
      4. Update job status in Redis
      5. Queue alert tasks if violations found

    Args:
        ctx: ARQ context — holds db session and detector.
        video_key: R2 object key of the uploaded video.
        site_id: Site this video belongs to.
        camera_id: Camera that captured it (optional).
        job_id: UUID for status tracking in Redis.

    Returns:
        dict with violation_count and violation_ids.
    """
    import boto3, io
    from botocore.config import Config
    from app.core.database import async_session_factory
    from app.core.storage import get_signed_url, upload_snapshot
    from app.crud.violation import create_violation
    from ml.inference.detector import PPEDetector
    from ml.inference.video_processor import VideoProcessor

    redis: ArqRedis = ctx["redis"]

    # Mark job as running
    await redis.set(f"job:{job_id}:status", "running", ex=3600)

    violation_ids: list[str] = []

    try:
        # --- Download video from R2 ---
        client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY,
            aws_secret_access_key=settings.R2_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            if settings.R2_BUCKET_NAME:
                client.download_fileobj(settings.R2_BUCKET_NAME, video_key, tmp)
            else:
                # Dev mode: treat video_key as a local path
                tmp_path = Path(video_key)

        # --- Load detector (cached in worker context) ---
        detector: PPEDetector = ctx.get("detector")
        if detector is None:
            model_path = Path("ml/models/ppe_yolo11.pt")
            if not model_path.exists():
                logger.error("Model weights missing — cannot process video")
                await redis.set(f"job:{job_id}:status", "failed:no_model", ex=3600)
                return {"violation_count": 0, "violation_ids": []}

            detector = PPEDetector(str(model_path))
            detector.load()
            ctx["detector"] = detector  # cache for next job

        processor = VideoProcessor(detector)

        # --- Process frames, save each violation ---
        import cv2
        cap = cv2.VideoCapture(str(tmp_path))

        async with async_session_factory() as db:
            for frame_idx, result in processor.process(tmp_path):
                # Re-read the actual frame for snapshot
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    continue

                snapshot_bytes = processor.extract_violation_snapshot(frame, result)
                snapshot_key, _ = await upload_snapshot(
                    snapshot_bytes,
                    site_id=site_id,
                    camera_id=camera_id,
                )
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
                violation_ids.append(violation.id)
                logger.info(
                    "Job %s: violation %s saved (frame %d, type=%s, conf=%.2f)",
                    job_id, violation.id, frame_idx,
                    result.primary_violation_type, result.max_confidence,
                )

        cap.release()
        tmp_path.unlink(missing_ok=True)  # clean up temp file

        # Mark job complete
        await redis.set(f"job:{job_id}:status", "complete", ex=3600)
        await redis.set(
            f"job:{job_id}:result",
            str({"violation_count": len(violation_ids), "violation_ids": violation_ids}),
            ex=3600,
        )

        # Queue alert tasks if violations found
        if violation_ids:
            await ctx["redis"].enqueue_job(
                "send_alert_task",
                site_id=site_id,
                violation_count=len(violation_ids),
            )

        return {"violation_count": len(violation_ids), "violation_ids": violation_ids}

    except Exception as e:
        logger.exception("Video processing failed for job %s: %s", job_id, e)
        await redis.set(f"job:{job_id}:status", f"failed:{type(e).__name__}", ex=3600)
        raise


async def send_alert_task(
    ctx: dict,
    *,
    site_id: str,
    violation_count: int,
) -> dict:
    """
    Send WhatsApp + email alerts for a batch of violations on a site.
    Phase 4 fills this out fully. Stub so the queue doesn't error.
    """
    logger.info("Alert task: site=%s violations=%d (Phase 4)", site_id, violation_count)
    return {"sent": False, "reason": "Phase 4 not yet implemented"}


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------

async def startup(ctx: dict) -> None:
    """Initialise resources shared across task executions."""
    from app.core.cache import cache
    await cache.connect()
    ctx["cache"] = cache
    logger.info("ARQ worker started")


async def shutdown(ctx: dict) -> None:
    """Clean up shared resources."""
    await ctx["cache"].disconnect()
    logger.info("ARQ worker stopped")


class WorkerSettings:
    """Discovered by: arq app.tasks.worker.WorkerSettings"""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [process_video_task, send_alert_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Enqueue helper (called from API endpoints)
# ---------------------------------------------------------------------------

async def enqueue_video_job(
    video_key: str,
    site_id: str,
    camera_id: str | None,
) -> str:
    """
    Enqueue a video processing job and return its job_id.
    Sets initial status in Redis so the polling endpoint returns immediately.
    """
    job_id = str(uuid.uuid4())
    redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))

    await redis.set(f"job:{job_id}:status", "queued", ex=3600)
    await redis.enqueue_job(
        "process_video_task",
        video_key=video_key,
        site_id=site_id,
        camera_id=camera_id,
        job_id=job_id,
    )
    await redis.aclose()
    return job_id
