"""
Level 1 Fine-Tuning — YOLOv8 on OR-Specific Data
===================================================
Takes frames collected by FrameSampler during pilots and fine-tunes
YOLOv8 for better person detection in operating-room environments.

Usage:
  python -m scripts.finetune_yolo \
    --data-dir ./training_data/OR-1 \
    --epochs 50 \
    --batch 16

Prerequisites:
  pip install ultralytics  (already in requirements)

Workflow:
  1. FrameSampler collects frames + annotations during pilot
  2. Review/label with a tool (CVAT, Label Studio, or the JSON annotations)
  3. Convert annotations to YOLO format (this script handles it)
  4. Fine-tune YOLOv8 with frozen backbone
  5. Export updated model for deployment
"""

import os
import sys
import json
import shutil
import random
import argparse
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def find_sessions(data_dir: str) -> List[Path]:
    """Find all session directories under the data root."""
    data_path = Path(data_dir)
    sessions = []
    for session_json in data_path.rglob("session.json"):
        sessions.append(session_json.parent)
    return sorted(sessions)


def convert_annotations_to_yolo(
    sessions: List[Path],
    output_dir: Path,
    train_split: float = 0.85,
) -> Tuple[int, int]:
    """Convert FrameSampler JSON annotations to YOLO txt format.

    YOLO format per line: <class_id> <x_center> <y_center> <width> <height>
    All values normalized 0-1. Class 0 = person.
    """
    images_train = output_dir / "images" / "train"
    images_val = output_dir / "images" / "val"
    labels_train = output_dir / "labels" / "train"
    labels_val = output_dir / "labels" / "val"

    for d in [images_train, images_val, labels_train, labels_val]:
        d.mkdir(parents=True, exist_ok=True)

    all_pairs = []  # (frame_path, annotation_path)

    for session in sessions:
        frames_dir = session / "frames"
        ann_dir = session / "annotations"

        if not frames_dir.exists():
            continue

        # Read session metadata for context
        session_meta_path = session / "session.json"
        if session_meta_path.exists():
            with open(session_meta_path) as f:
                meta = json.load(f)
            logger.info(
                f"Session {meta.get('session_id', '?')}: "
                f"{meta.get('total_frames', '?')} frames from {meta.get('or_number', '?')}"
            )

        for frame_file in sorted(frames_dir.iterdir()):
            if frame_file.suffix not in (".jpg", ".png"):
                continue

            ann_file = ann_dir / (frame_file.stem + ".json")
            if ann_file.exists():
                all_pairs.append((frame_file, ann_file))
            else:
                # Frame without annotation — skip (no bboxes)
                pass

    if not all_pairs:
        logger.error("No frame+annotation pairs found. Check your data directory.")
        return 0, 0

    # Shuffle and split
    random.shuffle(all_pairs)
    split_idx = int(len(all_pairs) * train_split)
    train_pairs = all_pairs[:split_idx]
    val_pairs = all_pairs[split_idx:]

    def _write_pair(frame_path: Path, ann_path: Path, img_dir: Path, lbl_dir: Path):
        """Copy frame and convert annotation to YOLO format."""
        # Read the image to get dimensions (from annotation metadata or infer)
        with open(ann_path) as f:
            annotation = json.load(f)

        # Need image dimensions — read from the image itself
        import cv2
        img = cv2.imread(str(frame_path))
        if img is None:
            return False
        h, w = img.shape[:2]

        # Copy image
        dest_img = img_dir / frame_path.name
        if not dest_img.exists():
            shutil.copy2(frame_path, dest_img)

        # Convert bboxes to YOLO format
        yolo_lines = []
        for person in annotation.get("persons", []):
            bbox = person.get("bbox")
            if not bbox or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            # Normalize to 0-1
            x_center = ((x1 + x2) / 2) / w
            y_center = ((y1 + y2) / 2) / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h

            # Clamp to [0, 1]
            x_center = max(0.0, min(1.0, x_center))
            y_center = max(0.0, min(1.0, y_center))
            bw = max(0.0, min(1.0, bw))
            bh = max(0.0, min(1.0, bh))

            # Class 0 = person
            yolo_lines.append(f"0 {x_center:.6f} {y_center:.6f} {bw:.6f} {bh:.6f}")

        # Write label file
        label_path = lbl_dir / (frame_path.stem + ".txt")
        with open(label_path, "w") as f:
            f.write("\n".join(yolo_lines))

        return True

    train_count = 0
    for fp, ap in train_pairs:
        if _write_pair(fp, ap, images_train, labels_train):
            train_count += 1

    val_count = 0
    for fp, ap in val_pairs:
        if _write_pair(fp, ap, images_val, labels_val):
            val_count += 1

    logger.info(f"Dataset prepared: {train_count} train, {val_count} val images")
    return train_count, val_count


def create_dataset_yaml(output_dir: Path) -> Path:
    """Create the data.yaml file required by YOLO training."""
    yaml_path = output_dir / "data.yaml"
    content = f"""# InfectionIQ OR Person Detection Dataset
# Auto-generated by finetune_yolo.py

path: {output_dir.resolve()}
train: images/train
val: images/val

# Classes
names:
  0: person
"""
    with open(yaml_path, "w") as f:
        f.write(content)

    logger.info(f"Dataset YAML: {yaml_path}")
    return yaml_path


def finetune(
    data_yaml: Path,
    epochs: int = 50,
    batch: int = 16,
    imgsz: int = 640,
    base_model: str = "yolov8n.pt",
    freeze_layers: int = 10,
    output_name: str = "infectioniq-person",
) -> str:
    """Fine-tune YOLOv8 with frozen backbone layers.

    Strategy:
    - Freeze the first N backbone layers (transfer learning)
    - Only train detection head on OR-specific data
    - Lower learning rate for stability
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    logger.info(f"Loading base model: {base_model}")
    model = YOLO(base_model)

    logger.info(f"Fine-tuning for {epochs} epochs (freeze={freeze_layers} layers)")
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        freeze=freeze_layers,
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=3,
        patience=10,
        name=output_name,
        exist_ok=True,
        verbose=True,
    )

    # Export to ONNX for deployment
    best_path = model.trainer.best
    logger.info(f"Best model: {best_path}")

    # Export
    export_path = model.export(format="onnx", imgsz=imgsz)
    logger.info(f"ONNX export: {export_path}")

    return str(best_path)


def main():
    parser = argparse.ArgumentParser(
        description="Level 1: Fine-tune YOLOv8 on OR-specific data from FrameSampler"
    )
    parser.add_argument(
        "--data-dir", type=str, required=True,
        help="Root directory with FrameSampler output (e.g. ./training_data/OR-1)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="./yolo_dataset",
        help="Where to write the converted YOLO dataset"
    )
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument(
        "--base-model", type=str, default="yolov8n.pt",
        help="Base YOLO model to fine-tune (default: yolov8n.pt)"
    )
    parser.add_argument("--freeze", type=int, default=10, help="Number of backbone layers to freeze")
    parser.add_argument("--train-split", type=float, default=0.85, help="Train/val split ratio")
    parser.add_argument(
        "--convert-only", action="store_true",
        help="Only convert annotations to YOLO format, don't train"
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)

    # Step 1: Find all sessions
    sessions = find_sessions(args.data_dir)
    if not sessions:
        logger.error(f"No sessions found in {args.data_dir}")
        sys.exit(1)
    logger.info(f"Found {len(sessions)} session(s)")

    # Step 2: Convert annotations to YOLO format
    train_count, val_count = convert_annotations_to_yolo(
        sessions, output_dir, train_split=args.train_split
    )
    if train_count == 0:
        logger.error("No training images produced. Check annotations.")
        sys.exit(1)

    # Step 3: Create dataset YAML
    data_yaml = create_dataset_yaml(output_dir)

    if args.convert_only:
        logger.info("Convert-only mode — skipping training.")
        logger.info(f"Dataset ready at: {output_dir}")
        logger.info(f"To train manually: yolo detect train data={data_yaml} epochs={args.epochs}")
        return

    # Step 4: Fine-tune
    best_model = finetune(
        data_yaml=data_yaml,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        base_model=args.base_model,
        freeze_layers=args.freeze,
    )

    logger.info(f"\nFine-tuning complete!")
    logger.info(f"Best model: {best_model}")
    logger.info(f"To use in InfectionIQ:")
    logger.info(f"  1. Copy {best_model} to cv_module/models/")
    logger.info(f"  2. Update PersonDetector model path")


if __name__ == "__main__":
    main()
