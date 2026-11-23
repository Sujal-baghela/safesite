"""Pydantic v2 schemas for violation request/response payloads."""

from datetime import datetime

from pydantic import BaseModel, Field


class DetectionItem(BaseModel):
    """Single bounding-box detection from YOLO inference."""
    class_name: str
    violation_type: str | None
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]
    is_violation: bool


class ImageInferenceResponse(BaseModel):
    """Response from POST /detect/image."""
    has_violation: bool
    violation_types: list[str]
    primary_violation_type: str
    max_confidence: float
    detections: list[DetectionItem]
    inference_ms: float
    violation_id: str | None = None   # set if a violation record was saved
    snapshot_url: str | None = None   # signed R2 URL


class VideoProcessResponse(BaseModel):
    """Response from POST /detect/video — job is async."""
    job_id: str
    status: str = "queued"
    message: str


class ViolationResponse(BaseModel):
    """Full violation record as returned to the frontend."""
    id: str
    camera_id: str | None
    site_id: str
    type: str
    confidence_score: float | None
    snapshot_url: str | None   # signed URL, resolved on read
    timestamp: datetime
    resolved: bool
    resolved_by: str | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ViolationListResponse(BaseModel):
    items: list[ViolationResponse]
    total: int
    page: int
    page_size: int


class ViolationResolveRequest(BaseModel):
    resolved: bool


class ViolationFilterParams(BaseModel):
    """Query parameters for violation list endpoint."""
    site_id: str | None = None
    camera_id: str | None = None
    type: str | None = None
    resolved: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
