"""
Video processing pipeline.

Extracts frames from a video file using OpenCV (or FFmpeg for speed),
runs YOLO11 batch inference, and yields InferenceResult per violation frame.

Design decisions:
  - Sample every Nth frame (default: every 15 frames at 30fps = 2 samples/sec)
    to avoid redundant detections of the same violation
  - Batch inference with batch_size=8 for throughput
  - Yields results as a generator so the ARQ task can stream DB inserts
    without loading all frames in memory at once
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Generator

import cv2
import numpy as np

from ml.inference.detector import InferenceResult, PPEDetector

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Extracts frames from a video and runs PPE detection on each sampled frame.

    Usage:
        processor = VideoProcessor(detector)
        for frame_idx, result in processor.process("path/to/video.mp4"):
            if result.has_violation:
                # save snapshot, create DB record
                ...
    """

    def __init__(
        self,
        detector: PPEDetector,
        sample_every_n_frames: int = 15,
        min_confidence: float = 0.45,
    ) -> None:
        """
        Args:
            detector: Loaded PPEDetector instance.
            sample_every_n_frames: Process 1 out of every N frames.
                15 at 30fps ≈ 2 samples/sec — enough to catch violations
                without redundant detections.
            min_confidence: Minimum confidence for a detection to trigger save.
        """
        self.detector = detector
        self.sample_every = sample_every_n_frames
        self.min_confidence = min_confidence

    def process(
        self,
        video_path: str | Path,
    ) -> Generator[tuple[int, InferenceResult], None, None]:
        """
        Process a video file, yielding (frame_index, InferenceResult) for
        every sampled frame that has at least one violation.

        Args:
            video_path: Path to the video file on disk.

        Yields:
            Tuples of (frame_index, InferenceResult) for violation frames only.

        Raises:
            FileNotFoundError: If the video file does not exist.
            RuntimeError: If OpenCV cannot open the video.
        """
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {path}")

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"OpenCV could not open video: {path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(
            "Processing video: %s | %.1f fps | %d total frames | sampling every %d",
            path.name, fps, total_frames, self.sample_every,
        )

        frame_buffer: list[tuple[int, np.ndarray]] = []
        frame_idx = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % self.sample_every == 0:
                    frame_buffer.append((frame_idx, frame.copy()))

                # Flush buffer when we have a full batch
                if len(frame_buffer) >= self.detector.BATCH_SIZE:
                    yield from self._flush_batch(frame_buffer)
                    frame_buffer.clear()

                frame_idx += 1

            # Flush remaining frames
            if frame_buffer:
                yield from self._flush_batch(frame_buffer)

        finally:
            cap.release()

        logger.info("Video processing complete: %d frames analysed", frame_idx)

    def _flush_batch(
        self,
        frame_buffer: list[tuple[int, np.ndarray]],
    ) -> Generator[tuple[int, InferenceResult], None, None]:
        """
        Run batch inference on buffered frames.
        Only yields frames that contain violations above min_confidence.
        """
        indices = [idx for idx, _ in frame_buffer]
        images = [frame for _, frame in frame_buffer]

        results = self.detector.predict_batch(images)

        for idx, result in zip(indices, results):
            if result.has_violation and result.max_confidence >= self.min_confidence:
                yield idx, result

    def extract_violation_snapshot(
        self,
        frame: np.ndarray,
        result: InferenceResult,
        jpeg_quality: int = 85,
    ) -> bytes:
        """
        Annotate a violation frame and encode it as JPEG bytes for R2 upload.

        Args:
            frame: Original BGR frame from OpenCV.
            result: InferenceResult containing bounding boxes to draw.
            jpeg_quality: JPEG compression quality (0-100).

        Returns:
            JPEG-encoded bytes of the annotated frame.
        """
        annotated = self.detector.annotate_frame(frame, result)
        _, jpeg_buf = cv2.imencode(
            ".jpg", annotated,
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
        )
        return jpeg_buf.tobytes()


def get_video_metadata(video_path: str | Path) -> dict:
    """
    Return basic metadata about a video file without processing it.

    Returns:
        Dict with fps, total_frames, duration_seconds, width, height.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {}

    metadata = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "duration_seconds": 0.0,
    }
    if metadata["fps"] > 0:
        metadata["duration_seconds"] = metadata["total_frames"] / metadata["fps"]

    cap.release()
    return metadata
