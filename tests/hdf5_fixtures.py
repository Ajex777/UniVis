"""Shared HDF5 fixtures for tests."""

from pathlib import Path

import h5py
import numpy as np

from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
)
from univis.utils.hdf5_episode import frames_to_qpos, write_string_dataset


def make_frame(index: int) -> PolicyFrame:
    """Create one synchronized dual-arm frame."""

    left = ArmFrame(
        xyz=[0.1 + index * 0.01, 0.2, 0.3],
        rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        gripper=0.2,
    )
    right = ArmFrame(
        xyz=[-0.1 - index * 0.01, -0.2, 0.3],
        rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        gripper=0.8,
    )
    return PolicyFrame(index=index, timestamp=index / 10.0, left=left, right=right)


def make_episode(episode_id: str = "episode-test", num_frames: int = 4) -> PolicyEpisode:
    """Create a small synchronized PolicyEpisode."""

    cameras = [
        CameraStream(key="cam_left_wrist", label="Left Wrist", width=8, height=6),
        CameraStream(key="cam_right_wrist", label="Right Wrist", width=8, height=6),
    ]
    metadata = PolicyEpisodeMetadata(
        episode_id=episode_id,
        title=episode_id,
        num_frames=num_frames,
        fps=10.0,
        cameras=cameras,
        annotation=Annotation(language_prompt="test prompt"),
    )
    return PolicyEpisode(
        metadata=metadata,
        frames=[make_frame(i) for i in range(num_frames)],
    )


def script_compatible_images(num_frames: int) -> dict[str, np.ndarray]:
    """Create deterministic BGR image frames using the converter layout."""

    frames = {}
    for cam_idx, cam_name in enumerate(("cam_left_wrist", "cam_right_wrist")):
        data = np.zeros((num_frames, 6, 8, 3), dtype=np.uint8)
        for frame_idx in range(num_frames):
            data[frame_idx, :, :, 0] = 20 + frame_idx + cam_idx
            data[frame_idx, :, :, 1] = 40 + frame_idx
            data[frame_idx, :, :, 2] = 60 + cam_idx
        frames[cam_name] = data
    return frames


def write_script_hdf5(path: Path, num_frames: int = 4) -> None:
    """Write HDF5 matching `pika_raw_to_compressed_hdf5.py` image structure."""

    episode = make_episode(num_frames=num_frames)
    qpos = frames_to_qpos(episode.frames[:num_frames])
    images = script_compatible_images(num_frames)
    with h5py.File(path, "w") as root:
        observations = root.create_group("observations")
        observations.create_dataset("qpos", data=qpos)
        root.create_dataset("action", data=qpos.copy())
        root.create_dataset("chunks", data=np.asarray(2, dtype=np.int32))
        write_string_dataset(root, "language_prompt", "script compatible prompt")
        image_group = observations.create_group("images")
        for cam_name, frames in images.items():
            image_group.create_dataset(f"{cam_name}_index", data=[0, 0, 1, 1])
            image_group.create_dataset(f"{cam_name}_start", data=[0, 2])
            camera = image_group.create_group(cam_name)
            camera.create_dataset("0", data=frames[:2].reshape(2, 6, 24))
            camera.create_dataset("1", data=frames[2:].reshape(2, 6, 24))
