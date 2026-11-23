"""
YOLO11 PPE detector — production implementation.

Wraps Ultralytics YOLO11 for PPE violation detection.
torch.compile() applied for ~30% faster repeated inference.
Designed to be instantiated once at startup and reused per-request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# PPE violation class names from the Construction Safety dataset (Roboflow)
# https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety
VIOLATION_CLASS_MAP: dict[str, str] = {
    "NO-Hardhat":     "no_helmet",
    "NO-Safety Vest": "no_vest",
    "NO-Gloves":      "no_gloves",
    "NO-Boots":       "no_boots",
    "NO-Mask":        "no_mask",
}

SAFE_CLASS_MAP: dict[str, str] = {
    "Hardhat":     "helmet",
    "Safety Vest": "vest",
    "Gloves":      "gloves",
    "Boots":       "boots",
    "Mask":        "mask",
    "Person":      "person",
}


@dataclass
class Detection:
    """Single object detection result from YOLO inference."""
    class_name: str           # raw YOLO class name
    violation_type: str | None  # maps to ViolationType enum, None if safe class
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    is_violation: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_violation = self.violation_type is not None

    def to_dict(self) -> dict:
        return {
            "class_name": self.class_name,
            "violation_type": self.violation_type,
            "confidence": round(self.confidence, 4),
            "bbox": list(self.bbox),
            "is_violation": self.is_violation,
        }


@dataclass
class InferenceResult:
    """Full result for one image/frame."""
    detections: list[Detection]
    violation_types: list[str]   # deduplicated violation types found
    has_violation: bool
    frame_width: int
    frame_height: int
    inference_ms: float

    @property
    def primary_violation_type(self) -> str:
        """Return the single violation type label for DB storage."""
        if not self.violation_types:
            return ""
        if len(self.violation_types) == 1:
            return self.violation_types[0]
        return "multiple"

    @property
    def max_confidence(self) -> float:
        """Highest confidence among violation detections."""
        violations = [d for d in self.detections if d.is_violation]
        return max((d.confidence for d in violations), default=0.0)

    def to_dict(self) -> dict:
        return {
            "detections": [d.to_dict() for d in self.detections],
            "violation_types": self.violation_types,
            "has_violation": self.has_violation,
            "primary_violation_type": self.primary_violation_type,
            "max_confidence": self.max_confidence,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "inference_ms": round(self.inference_ms, 2),
        }


class PPEDetector:
    """
    YOLO11-based PPE violation detector.

    Instantiate once at app startup, call predict() per frame.
    Uses torch.compile() on CUDA/MPS for best throughput.

    Usage:
        detector = PPEDetector("ml/models/ppe_yolo11.pt")
        detector.load()
        result = detector.predict(cv2.imread("frame.jpg"))
    """

    DEFAULT_MODEL_URL = (
        "https://universe.roboflow.com/roboflow-universe-projects/"
        "construction-site-safety"
    )
    BATCH_SIZE = 8  # sweet spot for CPU; increase to 16-32 on GPU

    def __init__(
        self,
        model_path: str | Path,
        device: str = "cpu",
        conf_threshold: float = 0.45,
        iou_threshold: float = 0.45,
    ) -> None:
        """
        Args:
            model_path: Path to YOLO11 .pt weights file.
            device: 'cpu', 'cuda', or 'mps'.
            conf_threshold: Minimum confidence for a detection to count.
            iou_threshold: NMS IoU threshold.
        """
        self.model_path = Path(model_path)
        self.device = device
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self._model = None
        self._loaded = False

    def load(self) -> None:
        """
        Load model weights and compile for speed.
        Call once at startup — not per request.
        """
        try:
            import torch
            from ultralytics import YOLO

            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Model weights not found at {self.model_path}. "
                    f"Download from: {self.DEFAULT_MODEL_URL}"
                )

            logger.info("Loading YOLO11 model from %s on %s", self.model_path, self.device)
            self._model = YOLO(str(self.model_path))
            self._model.to(self.device)

            # torch.compile gives ~30% speedup on repeated inference
            if self.device != "cpu" and hasattr(torch, "compile"):
                logger.info("Applying torch.compile() for GPU acceleration")
                self._model.model = torch.compile(self._model.model)

            # Warmup pass to trigger compilation / cache kernels
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(dummy, verbose=False)

            self._loaded = True
            logger.info("PPEDetector ready — model loaded")

        except ImportError as e:
            raise ImportError(
                "ultralytics and torch are required for inference. "
                "Install them: uv add ultralytics torch"
            ) from e

    def _ensure_loaded(self) -> None:
        if not self._loaded or self._model is None:
            raise RuntimeError("PPEDetector.load() must be called before predict()")

    def _parse_results(self, results, orig_h: int, orig_w: int) -> list[Detection]:
        """Convert Ultralytics Results object to Detection dataclasses."""
        detections: list[Detection] = []
        names: dict[int, str] = results.names  # {0: "Hardhat", 1: "NO-Hardhat", ...}

        if results.boxes is None:
            return detections

        for box in results.boxes:
            class_id = int(box.cls.item())
            class_name = names.get(class_id, str(class_id))
            confidence = float(box.conf.item())

            # x1 y1 x2 y2 in pixel coordinates
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            violation_type = VIOLATION_CLASS_MAP.get(class_name)
            # Also keep safe detections for context
            if violation_type is None and class_name not in SAFE_CLASS_MAP:
                continue  # unknown class — skip

            detections.append(Detection(
                class_name=class_name,
                violation_type=violation_type,
                confidence=confidence,
                bbox=(float(x1), float(y1), float(x2), float(y2)),
            ))

        return detections

    def predict(self, image: np.ndarray) -> InferenceResult:
        """
        Run inference on a single BGR image (OpenCV format).

        Args:
            image: numpy array shape (H, W, 3), dtype uint8, BGR.

        Returns:
            InferenceResult with all detections and violation summary.
        """
        import time
        self._ensure_loaded()

        h, w = image.shape[:2]
        t0 = time.perf_counter()

        results = self._model.predict(
            image,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False,
        )[0]

        elapsed_ms = (time.perf_counter() - t0) * 1000
        detections = self._parse_results(results, h, w)
        violation_types = list({
            d.violation_type for d in detections if d.is_violation
        })

        return InferenceResult(
            detections=detections,
            violation_types=violation_types,
            has_violation=bool(violation_types),
            frame_width=w,
            frame_height=h,
            inference_ms=elapsed_ms,
        )

    def predict_batch(self, images: list[np.ndarray]) -> list[InferenceResult]:
        """
        Run inference on a batch of images for higher throughput.
        Processes in chunks of BATCH_SIZE.

        Args:
            images: List of BGR numpy arrays (can be different sizes).

        Returns:
            List of InferenceResult, one per input image.
        """
        self._ensure_loaded()
        results_out: list[InferenceResult] = []

        for i in range(0, len(images), self.BATCH_SIZE):
            batch = images[i: i + self.BATCH_SIZE]
            batch_results = self._model.predict(
                batch,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )
            for img, res in zip(batch, batch_results):
                h, w = img.shape[:2]
                detections = self._parse_results(res, h, w)
                vt = list({d.violation_type for d in detections if d.is_violation})
                results_out.append(InferenceResult(
                    detections=detections,
                    violation_types=vt,
                    has_violation=bool(vt),
                    frame_width=w,
                    frame_height=h,
                    inference_ms=0.0,  # batch timing less meaningful
                ))

        return results_out

    def annotate_frame(self, image: np.ndarray, result: InferenceResult) -> np.ndarray:
        """
        Draw bounding boxes and labels onto a copy of the frame.
        Red for violations, green for safe PPE.

        Args:
            image: Original BGR frame.
            result: InferenceResult from predict().

        Returns:
            Annotated BGR frame (new array — original unchanged).
        """
        annotated = image.copy()
        for det in result.detections:
            x1, y1, x2, y2 = (int(v) for v in det.bbox)
            color = (0, 0, 220) if det.is_violation else (0, 200, 0)  # BGR
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            cv2.putText(
                annotated, label,
                (x1, max(y1 - 8, 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
            )
        return annotated
