"""Dexforce W1 teleop episode discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path

from univis.formats.dexforce_w1_teleop.settings import W1CameraConfig, W1TeleopConfig
from univis.utils.json_io import read_json, write_json
from univis.utils.sorting import natural_sort_key
from univis.domain.policy_episode import Annotation


@dataclass(frozen=True)
class W1EpisodeManifest:
    """Resolved paths and config for one W1 teleop episode."""

    episode_dir: Path
    metadata_path: Path
    qpos_path: Path
    cameras: tuple[W1CameraConfig, ...]


def scan_w1_episode(
    episode_dir: Path,
    config: W1TeleopConfig,
) -> W1EpisodeManifest:
    """Validate and resolve one W1 teleop episode directory."""

    root = Path(episode_dir).expanduser().resolve()
    metadata_path = root / config.metadata_file
    if not metadata_path.exists():
        raise FileNotFoundError(f"missing W1 metadata file: {metadata_path}")
    qpos_files = sorted(root.glob(config.qpos_pattern), key=lambda path: natural_sort_key(path.name))
    if not qpos_files:
        raise FileNotFoundError(f"missing W1 qpos file matching {config.qpos_pattern}: {root}")
    return W1EpisodeManifest(
        episode_dir=root,
        metadata_path=metadata_path,
        qpos_path=qpos_files[0],
        cameras=config.cameras,
    )


def is_w1_episode_dir(path: Path, config: W1TeleopConfig) -> bool:
    """Return whether a directory looks like one W1 teleop episode."""

    try:
        scan_w1_episode(path, config)
        return True
    except Exception:
        return False


def collect_w1_episode_dirs(root: Path, config: W1TeleopConfig) -> list[Path]:
    """Collect naturally sorted W1 episode dirs from a root or single episode."""

    path = Path(root).expanduser().resolve()
    if path.is_dir() and is_w1_episode_dir(path, config):
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"W1 teleop source not found: {path}")
    episodes = [
        child
        for child in path.iterdir()
        if child.is_dir()
        and fnmatch.fnmatch(child.name, config.episode_pattern)
        and is_w1_episode_dir(child, config)
    ]
    return sorted(episodes, key=lambda item: natural_sort_key(item.name))


def load_annotation(episode_dir: Path, config: W1TeleopConfig) -> Annotation:
    """Load language prompt from the qpos JSON top-level field."""

    manifest = scan_w1_episode(episode_dir, config)
    try:
        payload = read_json(manifest.qpos_path)
    except Exception:
        return Annotation()
    prompt = payload.get(config.instruction_field, "") if isinstance(payload, dict) else ""
    return Annotation(language_prompt=str(prompt or ""))


def write_annotation(
    episode_dir: Path,
    annotation: Annotation,
    config: W1TeleopConfig,
) -> None:
    """Write prompt and UniVis review state back to the qpos JSON file."""

    manifest = scan_w1_episode(episode_dir, config)
    payload = read_json(manifest.qpos_path)
    if not isinstance(payload, dict):
        payload = {}
    payload[config.instruction_field] = annotation.language_prompt
    payload["univis_annotation"] = annotation.model_dump()
    write_json(manifest.qpos_path, payload)
