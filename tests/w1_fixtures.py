"""Shared Dexforce W1 teleop fixtures for adapter tests."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

JOINT_ORDER = [
    "ANKLE", "KNEE", "BUTTOCK", "WAIST", "NECK1", "NECK2",
    "LEFT_J1", "LEFT_J2", "LEFT_J3", "LEFT_J4", "LEFT_J5", "LEFT_J6", "LEFT_J7",
    "LEFT_GRIPPER", "RIGHT_J1", "RIGHT_J2", "RIGHT_J3", "RIGHT_J4", "RIGHT_J5",
    "RIGHT_J6", "RIGHT_J7", "RIGHT_GRIPPER", "LEFT_HAND_THUMB1", "LEFT_HAND_THUMB2",
    "LEFT_HAND_INDEX", "LEFT_HAND_MIDDLE", "LEFT_HAND_RING", "LEFT_HAND_PINKY",
    "RIGHT_HAND_THUMB1", "RIGHT_HAND_THUMB2", "RIGHT_HAND_INDEX", "RIGHT_HAND_MIDDLE",
    "RIGHT_HAND_RING", "RIGHT_HAND_PINKY",
]


def write_w1_teleop_episode(root: Path, episode_name: str = "session0", frames: int = 6) -> Path:
    """Create a minimal W1 teleop episode tree.

    Inputs:
        root: Parent directory receiving the episode directory.
        episode_name: Directory name.
        frames: Number of timestamped frames.
    Output:
        Generated episode path.
    """

    episode = root / episode_name
    for rel in ("head/left", "head/right", "hand/left", "hand/right"):
        (episode / rel).mkdir(parents=True, exist_ok=True)

    metadata_rows = []
    for idx in range(frames):
        timestamp = 10.0 + idx * 0.1
        name = f"{idx:06d}.png"
        for camera_type, rel in (
            ("head_left", "head/left"),
            ("head_right", "head/right"),
            ("hand_left", "hand/left"),
            ("hand_right", "hand/right"),
        ):
            _write_image(episode / rel / name, idx, camera_type)
            metadata_rows.append({
                "timestamp": timestamp,
                "camera_type": camera_type,
                "image_path": f"{rel}/{name}",
            })
    (episode / "metadata.jsonl").write_text(
        "\n".join(json.dumps(row) for row in metadata_rows) + "\n",
        encoding="utf-8",
    )
    _write_qpos(episode / "pose_record_test.json", frames)
    return episode


def _write_image(path: Path, idx: int, camera_type: str) -> None:
    color = (idx * 20 % 255, len(camera_type) * 10 % 255, 120)
    Image.new("RGB", (9, 7), color).save(path)


def _write_qpos(path: Path, frames: int) -> None:
    rows = []
    for idx in range(frames):
        data = {name: float(idx + joint_idx / 100.0) for joint_idx, name in enumerate(JOINT_ORDER)}
        data["WAIST"] = float(0.5 + idx)
        data["LEFT_GRIPPER"] = float(idx / max(1, frames - 1))
        data["RIGHT_GRIPPER"] = float(1.0 - idx / max(1, frames - 1))
        rows.append({"frame_id": idx, "timestamp": 10.0 + idx * 0.1, "data": data})
    path.write_text(
        json.dumps({"language_prompt": "w1 prompt", "frames": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
