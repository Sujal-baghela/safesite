"""
Download YOLO11 PPE detection weights from Roboflow.

Usage:
    python ml/models/download_weights.py --api-key YOUR_ROBOFLOW_API_KEY

The Construction Safety dataset on Roboflow (8 classes):
  Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest,
  Gloves, NO-Gloves, Person, Boots, Mask

Dataset: https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety

Alternatively, train your own:
    yolo train data=construction-safety.yaml model=yolo11n.pt epochs=50 imgsz=640
"""

import argparse
import sys
from pathlib import Path


def download_from_roboflow(api_key: str, output_dir: Path) -> None:
    """
    Download pre-trained YOLOv8/YOLO11 weights via the Roboflow API.
    Saves to ml/models/ppe_yolo11.pt
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        print("Install roboflow: pip install roboflow")
        sys.exit(1)

    rf = Roboflow(api_key=api_key)
    project = rf.workspace("roboflow-universe-projects").project("construction-site-safety")
    version = project.version(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    version.download("yolov8", location=str(output_dir))
    print(f"Weights downloaded to {output_dir}")
    print("Rename the .pt file to: ml/models/ppe_yolo11.pt")


def download_pretrained_nano() -> None:
    """
    Download the base YOLO11n pretrained weights (COCO) as a starting point.
    Fine-tuning on the PPE dataset is then needed.
    """
    from ultralytics import YOLO

    output_path = Path("ml/models/yolo11n.pt")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO("yolo11n.pt")  # downloads from Ultralytics CDN
    model.save(str(output_path))
    print(f"Base YOLO11n weights saved to {output_path}")
    print("Next step: fine-tune with ml/training/train.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download PPE detection model weights")
    parser.add_argument("--api-key", help="Roboflow API key")
    parser.add_argument(
        "--pretrained-only",
        action="store_true",
        help="Download base YOLO11n weights only (no Roboflow account needed)",
    )
    args = parser.parse_args()

    models_dir = Path(__file__).parent

    if args.pretrained_only:
        download_pretrained_nano()
    elif args.api_key:
        download_from_roboflow(args.api_key, models_dir)
    else:
        print("Provide --api-key or use --pretrained-only")
        print("Example: python ml/models/download_weights.py --pretrained-only")
        sys.exit(1)
