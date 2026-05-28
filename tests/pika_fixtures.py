"""Shared PIKA raw fixtures for adapter tests."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


def write_pika_raw_episode(root: Path, episode_name: str = "episode0", frames: int = 56) -> Path:
    """Create a small PIKA raw episode tree.

    Inputs:
        root: Parent directory receiving the episode.
        episode_name: Episode directory name.
        frames: Number of timestamped samples to generate.
    Output:
        Path to the generated episode directory.
    """

    episode = root / episode_name
    left_cam = episode / "camera" / "color" / "pikaDepthCamera_l"
    right_cam = episode / "camera" / "color" / "pikaDepthCamera_r"
    left_pose = episode / "localization" / "pose" / "pika_l"
    right_pose = episode / "localization" / "pose" / "pika_r"
    left_grip = episode / "gripper" / "encoder" / "pika_l"
    right_grip = episode / "gripper" / "encoder" / "pika_r"
    for directory in (left_cam, right_cam, left_pose, right_pose, left_grip, right_grip):
        directory.mkdir(parents=True, exist_ok=True)
    (episode / "instructions.json").write_text(
        json.dumps({"instruction": "raw prompt"}, ensure_ascii=False),
        encoding="utf-8",
    )

    for idx in range(frames):
        timestamp = f"{1000.0 + idx * 0.1:.6f}"
        _write_image(left_cam / f"{timestamp}.png", idx, right=False)
        _write_image(right_cam / f"{timestamp}.png", idx, right=True)
        _write_pose(left_pose / f"{timestamp}.json", idx, scale=1.0)
        _write_pose(right_pose / f"{timestamp}.json", idx, scale=-1.0)
        _write_gripper(left_grip / f"{timestamp}.json", idx)
        _write_gripper(right_grip / f"{timestamp}.json", frames - idx - 1)
    return episode


def _write_image(path: Path, idx: int, right: bool) -> None:
    color = (idx % 255, 64 + int(right) * 40, 180 - int(right) * 30)
    Image.new("RGB", (8, 6), color).save(path)


def _write_pose(path: Path, idx: int, scale: float) -> None:
    payload = {
        "x": 0.01 * idx * scale,
        "y": 0.002 * idx,
        "z": 0.3,
        "roll": 0.001 * idx,
        "pitch": 0.0,
        "yaw": 0.002 * idx * scale,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_gripper(path: Path, idx: int) -> None:
    distance = min(0.095, max(0.0, 0.095 * (idx / 60.0)))
    path.write_text(json.dumps({"distance": distance}), encoding="utf-8")
