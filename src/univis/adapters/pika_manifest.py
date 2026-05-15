"""PIKA raw episode discovery and instruction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path
from typing import Any

from univis.utils.json_io import read_json, write_json
from univis.utils.sorting import natural_sort_key

CAM_LEFT_WRIST = "cam_left_wrist"
CAM_RIGHT_WRIST = "cam_right_wrist"
DEFAULT_PATTERN = "episode*"


@dataclass(frozen=True)
class PikaEpisodeManifest:
    """Resolved paths for one PIKA raw episode."""

    episode_dir: Path
    left_camera_dir: Path
    right_camera_dir: Path
    left_pose_dir: Path
    right_pose_dir: Path
    left_gripper_dir: Path
    right_gripper_dir: Path
    instruction_path: Path | None


def scan_pika_episode(episode_dir: Path) -> PikaEpisodeManifest:
    """Validate and resolve one PIKA raw episode directory."""

    root = Path(episode_dir).expanduser().resolve()
    required = {
        "left_camera_dir": root / "camera" / "color" / "pikaDepthCamera_l",
        "right_camera_dir": root / "camera" / "color" / "pikaDepthCamera_r",
        "left_pose_dir": root / "localization" / "pose" / "pika_l",
        "right_pose_dir": root / "localization" / "pose" / "pika_r",
        "left_gripper_dir": root / "gripper" / "encoder" / "pika_l",
        "right_gripper_dir": root / "gripper" / "encoder" / "pika_r",
    }
    for name, path in required.items():
        if not path.exists():
            raise FileNotFoundError(f"missing required PIKA path {name}: {path}")
    instruction = root / "instructions.json"
    return PikaEpisodeManifest(
        episode_dir=root,
        instruction_path=instruction if instruction.exists() else None,
        **required,
    )


def is_pika_episode_dir(path: Path) -> bool:
    """Return whether a path looks like one PIKA raw episode."""

    try:
        scan_pika_episode(path)
        return True
    except Exception:
        return False


def collect_pika_episode_dirs(root: Path, pattern: str = DEFAULT_PATTERN) -> list[Path]:
    """Collect naturally sorted PIKA episodes from a root or single episode path."""

    path = Path(root).expanduser().resolve()
    if path.is_dir() and is_pika_episode_dir(path):
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"PIKA source not found: {path}")
    episodes = [
        child
        for child in path.iterdir()
        if child.is_dir()
        and fnmatch.fnmatch(child.name, pattern)
        and is_pika_episode_dir(child)
    ]
    return sorted(episodes, key=lambda item: natural_sort_key(item.name))


def load_instruction(episode_dir: Path) -> str:
    """Extract the first language instruction from `instructions.json`."""

    path = Path(episode_dir) / "instructions.json"
    if not path.exists():
        return ""
    try:
        return _extract_text(read_json(path))
    except Exception:
        return ""


def write_instruction(episode_dir: Path, language_prompt: str) -> None:
    """Write an updated prompt back to `instructions.json`."""

    path = Path(episode_dir) / "instructions.json"
    payload: Any = {}
    if path.exists():
        try:
            payload = read_json(path)
        except Exception:
            payload = {}
    write_json(path, _set_text(payload, language_prompt))


def _extract_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        return next((text for item in payload if (text := _extract_text(item))), "")
    if isinstance(payload, dict):
        for key in ("instruction", "text", "prompt", "language_prompt"):
            if key in payload and (text := _extract_text(payload[key])):
                return text
        return next((text for value in payload.values() if (text := _extract_text(value))), "")
    return ""


def _set_text(payload: Any, text: str) -> Any:
    if isinstance(payload, str):
        return text
    if isinstance(payload, list) and payload:
        payload[0] = _set_text(payload[0], text)
        return payload
    if isinstance(payload, dict):
        for key in ("instruction", "text", "prompt", "language_prompt"):
            if key in payload:
                payload[key] = _set_text(payload[key], text)
                return payload
        payload["language_prompt"] = text
        return payload
    return {"language_prompt": text}
