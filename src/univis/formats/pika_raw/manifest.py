"""PIKA raw episode discovery and instruction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path
from typing import Any

from univis.domain.policy_episode import Annotation
from univis.formats.pika_raw.settings import PikaRawFormatConfig
from univis.utils.json_io import read_json, write_json
from univis.utils.sorting import natural_sort_key

DEFAULT_CONFIG = PikaRawFormatConfig.load()
CAM_LEFT_WRIST = DEFAULT_CONFIG.layout.left_camera.key
CAM_RIGHT_WRIST = DEFAULT_CONFIG.layout.right_camera.key
DEFAULT_PATTERN = DEFAULT_CONFIG.layout.episode_pattern


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
    left_camera_key: str
    right_camera_key: str
    left_camera_label: str
    right_camera_label: str
    left_camera_suffixes: tuple[str, ...]
    right_camera_suffixes: tuple[str, ...]
    pose_fields: tuple[str, ...]
    instruction_path: Path | None


def scan_pika_episode(
    episode_dir: Path,
    config: PikaRawFormatConfig | None = None,
) -> PikaEpisodeManifest:
    """Validate and resolve one PIKA raw episode directory."""

    cfg = config or DEFAULT_CONFIG
    layout = cfg.layout
    root = Path(episode_dir).expanduser().resolve()
    required = {
        "left_camera_dir": root / layout.left_camera.path,
        "right_camera_dir": root / layout.right_camera.path,
        "left_pose_dir": root / layout.left_pose_path,
        "right_pose_dir": root / layout.right_pose_path,
        "left_gripper_dir": root / layout.left_gripper_path,
        "right_gripper_dir": root / layout.right_gripper_path,
    }
    for name, path in required.items():
        if not path.exists():
            raise FileNotFoundError(f"missing required PIKA path {name}: {path}")
    instruction = root / layout.instruction_file
    return PikaEpisodeManifest(
        episode_dir=root,
        instruction_path=instruction if instruction.exists() else None,
        left_camera_key=layout.left_camera.key,
        right_camera_key=layout.right_camera.key,
        left_camera_label=layout.left_camera.label,
        right_camera_label=layout.right_camera.label,
        left_camera_suffixes=layout.left_camera.suffixes,
        right_camera_suffixes=layout.right_camera.suffixes,
        pose_fields=layout.pose_fields,
        **required,
    )


def is_pika_episode_dir(path: Path, config: PikaRawFormatConfig | None = None) -> bool:
    """Return whether a path looks like one PIKA raw episode."""

    try:
        scan_pika_episode(path, config)
        return True
    except Exception:
        return False


def collect_pika_episode_dirs(
    root: Path,
    config: PikaRawFormatConfig | None = None,
) -> list[Path]:
    """Collect naturally sorted PIKA episodes from a root or single episode path."""

    cfg = config or DEFAULT_CONFIG
    path = Path(root).expanduser().resolve()
    if path.is_dir() and is_pika_episode_dir(path, cfg):
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"PIKA source not found: {path}")
    episodes = [
        child
        for child in path.iterdir()
        if child.is_dir()
        and fnmatch.fnmatch(child.name, cfg.layout.episode_pattern)
        and is_pika_episode_dir(child, cfg)
    ]
    return sorted(episodes, key=lambda item: natural_sort_key(item.name))


def load_instruction(
    episode_dir: Path,
    config: PikaRawFormatConfig | None = None,
) -> str:
    """Extract the first language instruction from `instructions.json`."""

    return load_annotation(episode_dir, config).language_prompt


def write_instruction(
    episode_dir: Path,
    language_prompt: str,
    config: PikaRawFormatConfig | None = None,
) -> None:
    """Write an updated prompt back to `instructions.json`."""

    saved = load_annotation(episode_dir, config).model_copy(update={"language_prompt": language_prompt})
    write_annotation(episode_dir, saved, config)


def load_annotation(
    episode_dir: Path,
    config: PikaRawFormatConfig | None = None,
) -> Annotation:
    """Load UniVis annotation metadata from a PIKA raw episode.

    Inputs:
        episode_dir: PIKA episode directory.
    Output:
        Annotation with prompt from legacy fields and review state from the
        optional `univis_annotation` payload.
    """

    path = _instruction_path(episode_dir, config)
    if not path.exists():
        return Annotation()
    try:
        payload = read_json(path)
        base = _extract_univis_annotation(payload)
        base["language_prompt"] = _extract_text(payload) or base.get("language_prompt", "")
        return Annotation(**base)
    except Exception:
        return Annotation()


def write_annotation(
    episode_dir: Path,
    annotation: Annotation,
    config: PikaRawFormatConfig | None = None,
) -> None:
    """Persist prompt plus review metadata in `instructions.json`.

    Inputs:
        episode_dir: PIKA episode directory.
        annotation: Full UniVis annotation state.
    Output:
        Mutates or creates `instructions.json`.
    """

    path = _instruction_path(episode_dir, config)
    payload: Any = {}
    if path.exists():
        try:
            payload = read_json(path)
        except Exception:
            payload = {}
    updated = _set_text(payload, annotation.language_prompt)
    if isinstance(updated, dict):
        updated["univis_annotation"] = annotation.model_dump()
    else:
        updated = {
            "language_prompt": annotation.language_prompt,
            "univis_annotation": annotation.model_dump(),
        }
    write_json(path, updated)


def _instruction_path(episode_dir: Path, config: PikaRawFormatConfig | None = None) -> Path:
    """Return the configured instruction metadata path for one episode."""

    cfg = config or DEFAULT_CONFIG
    return Path(episode_dir) / cfg.layout.instruction_file


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


def _extract_univis_annotation(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("univis_annotation"), dict):
        return dict(payload["univis_annotation"])
    return {}
