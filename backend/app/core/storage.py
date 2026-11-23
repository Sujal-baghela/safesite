"""
Cloudflare R2 object storage module.

Handles:
  - Uploading violation snapshot images
  - Generating short-lived signed URLs (1-hour expiry)
  - Caching signed URLs in Redis to avoid regeneration on every request
"""

import logging
import uuid
from datetime import datetime
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.cache import TTL_R2_SIGNED_URL, cache
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _make_client():
    """Build an S3-compatible boto3 client pointing at Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
        region_name="auto",
    )


def _snapshot_key(site_id: str, camera_id: str | None, ext: str = "jpg") -> str:
    """
    Build a deterministic R2 object key for a violation snapshot.

    Format: violations/<site_id>/<camera_id>/<uuid>.<ext>
    """
    cam = camera_id or "upload"
    date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
    unique = uuid.uuid4().hex[:12]
    return f"violations/{site_id}/{cam}/{date_prefix}/{unique}.{ext}"


async def upload_snapshot(
    image_bytes: bytes,
    site_id: str,
    camera_id: str | None = None,
    content_type: str = "image/jpeg",
) -> tuple[str, str]:
    """
    Upload a violation snapshot image to Cloudflare R2.

    Args:
        image_bytes: Raw JPEG/PNG bytes of the snapshot.
        site_id: ID of the site this snapshot belongs to.
        camera_id: Optional camera ID for path organisation.
        content_type: MIME type of the image.

    Returns:
        Tuple of (object_key, public_url_or_empty).

    Raises:
        RuntimeError: If upload fails after retries.
    """
    if not settings.R2_BUCKET_NAME:
        logger.warning("R2 not configured — snapshot not uploaded")
        return ("", "")

    key = _snapshot_key(site_id, camera_id)
    client = _make_client()

    try:
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
            Metadata={
                "site_id": site_id,
                "camera_id": camera_id or "",
            },
        )
        logger.info("Uploaded snapshot: %s (%d bytes)", key, len(image_bytes))
        return key, ""
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"R2 upload failed for key={key}: {e}") from e


async def get_signed_url(object_key: str) -> str:
    """
    Return a signed URL for a snapshot, using Redis cache to avoid
    regenerating on every request.

    Cached for 50 minutes (R2 expiry is 60 minutes — 10 min safety buffer).

    Args:
        object_key: The R2 object key returned from upload_snapshot().

    Returns:
        Presigned HTTPS URL valid for ~1 hour, or empty string on error.
    """
    if not object_key or not settings.R2_BUCKET_NAME:
        return ""

    cache_key = cache.key_signed_url(object_key)
    cached_url = await cache.get(cache_key)
    if cached_url:
        return cached_url

    client = _make_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": object_key},
            ExpiresIn=settings.R2_SIGNED_URL_EXPIRY,
        )
        await cache.set(cache_key, url, ttl=TTL_R2_SIGNED_URL)
        return url
    except (BotoCoreError, ClientError) as e:
        logger.error("Failed to generate signed URL for %s: %s", object_key, e)
        return ""


async def delete_snapshot(object_key: str) -> bool:
    """
    Delete a snapshot from R2 and evict its cached signed URL.

    Returns True on success, False on error.
    """
    if not object_key or not settings.R2_BUCKET_NAME:
        return False

    client = _make_client()
    try:
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_key)
        await cache.delete(cache.key_signed_url(object_key))
        logger.info("Deleted snapshot: %s", object_key)
        return True
    except (BotoCoreError, ClientError) as e:
        logger.error("Failed to delete snapshot %s: %s", object_key, e)
        return False
