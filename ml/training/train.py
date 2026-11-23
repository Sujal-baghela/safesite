"""
Fine-tune YOLO11 on the Construction Safety PPE dataset.

Usage:
    python ml/training/train.py \
        --data path/to/construction-safety.yaml \
        --epochs 50 \
        --batch 16 \
        --device cpu

Export after training:
    python ml/training/train.py --export --model runs/detect/train/weights/best.pt
"""

import argparse
from pathlib import Path


def train(
    data_yaml: str,
    base_model: str = "yolo11n.pt",
    epochs: int = 50,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "cpu",
    project: str = "runs/detect",
    name: str = "safesite_ppe",
) -> None:
    """
    Fine-tune YOLO11 on a PPE dataset.

    Args:
        data_yaml: Path to dataset YAML (Roboflow export format).
        base_model: Starting weights — 'yolo11n.pt' (nano) or 'yolo11s.pt' (small).
        epochs: Training epochs.
        batch: Batch size (reduce if OOM on CPU).
        imgsz: Input image size for training.
        device: 'cpu', '0' (first GPU), 'mps' (Apple Silicon).
        project: Output directory root.
        name: Run name within project.
    """
    from ultralytics import YOLO

    model = YOLO(base_model)

    results = model.train(
        data=data_yaml,
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        project=project,
        name=name,
        # Augmentation — helps with varied site lighting
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        # Save best weights
        save=True,
        save_period=10,
    )

    best_weights = Path(project) / name / "weights" / "best.pt"
    print(f"\nTraining complete. Best weights: {best_weights}")
    print(f"Copy to ml/models/ppe_yolo11.pt:\n  cp {best_weights} ml/models/ppe_yolo11.pt")
    return results


def export_model(model_path: str, format: str = "onnx") -> None:
    """
    Export trained weights to ONNX or other formats for deployment.

    Args:
        model_path: Path to .pt weights.
        format: Export format — 'onnx', 'torchscript', 'coreml'.
    """
    from ultralytics import YOLO
    model = YOLO(model_path)
    model.export(format=format, imgsz=640, simplify=True)
    print(f"Exported to {format} format")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO11 PPE detector")
    parser.add_argument("--data", default="construction-safety.yaml")
    parser.add_argument("--base-model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--model", help="Model path for export")
    args = parser.parse_args()

    if args.export:
        if not args.model:
            print("Provide --model path for export")
        else:
            export_model(args.model)
    else:
        train(
            data_yaml=args.data,
            base_model=args.base_model,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
        )
