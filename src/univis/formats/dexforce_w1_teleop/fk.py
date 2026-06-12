"""Minimal Dexforce W1 FK helper without importing dexechain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from univis.formats.dexforce_w1_teleop.settings import W1TeleopConfig


@dataclass(frozen=True)
class W1FKBatchResult:
    """Batched dual-arm FK output.

    Inputs:
        left/right arrays with shape `(T, 9)` containing xyz + rot6d.
    Output:
        Numpy payload consumed by the W1 adapter.
    """

    left: np.ndarray
    right: np.ndarray


class W1ForwardKinematics:
    """Compute W1 EEF FK from full qpos using local URDF + pytorch_kinematics."""

    def __init__(self, config: W1TeleopConfig) -> None:
        """Initialize with config; heavy FK dependencies are loaded lazily."""

        self.config = config
        self._chains: dict[str, object] | None = None

    def compute_dual_arm_eef_batch(self, full_qpos: np.ndarray) -> W1FKBatchResult:
        """Convert full W1 qpos rows into left/right xyz + rot6d arrays."""

        qpos = np.asarray(full_qpos, dtype=np.float32)
        if qpos.ndim != 2:
            raise ValueError(f"expected qpos shape (T, D), got {qpos.shape}")
        chains = self._load_chains()
        left_input = self._arm_input(qpos, "left")
        right_input = self._arm_input(qpos, "right")
        return W1FKBatchResult(
            left=self._run_fk(chains["left"], left_input),
            right=self._run_fk(chains["right"], right_input),
        )

    def _arm_input(self, qpos: np.ndarray, side: str) -> np.ndarray:
        """Build one arm FK input from full qpos according to `has_waist`."""

        arm = self.config.left_arm if side == "left" else self.config.right_arm
        parts = []
        if self.config.kinematics.has_waist:
            parts.append(qpos[:, self.config.indices_for(self.config.waist_joint_names)])
        parts.append(qpos[:, self.config.indices_for(arm.joint_names)])
        return np.concatenate(parts, axis=1).astype(np.float32)

    def _load_chains(self) -> dict[str, object]:
        """Build and cache pytorch_kinematics SerialChains from configured URDF."""

        if self._chains is not None:
            return self._chains
        try:
            import pytorch_kinematics as pk
        except Exception as exc:
            raise RuntimeError(
                "W1 FK requires optional dependencies. Start UniVis with "
                "`uv run --extra w1-fk univis ...` or install the `w1-fk` extra."
            ) from exc
        urdf_path = Path(self.config.kinematics.urdf_path).expanduser()
        if not urdf_path.exists():
            raise FileNotFoundError(
                "W1 FK URDF not found. Set `kinematics.urdf_path` in "
                "`src/univis/formats/dexforce_w1_teleop/config/default.yaml` "
                "or pass a W1 config with a valid local URDF path."
            )
        chain = pk.build_chain_from_urdf(urdf_path.read_bytes())
        kin = self.config.kinematics
        left_root = kin.waist_root if kin.has_waist else kin.left_root_without_waist
        right_root = kin.waist_root if kin.has_waist else kin.right_root_without_waist
        self._chains = {
            "left": _serial_chain(pk, chain, kin.left_end_frame, left_root),
            "right": _serial_chain(pk, chain, kin.right_end_frame, right_root),
        }
        return self._chains

    def _run_fk(self, chain: object, qpos: np.ndarray) -> np.ndarray:
        """Run FK and convert transform matrices to xyz + rot6d."""

        try:
            import torch
        except Exception as exc:
            raise RuntimeError(
                "W1 FK requires optional dependencies. Start UniVis with "
                "`uv run --extra w1-fk univis ...` or install the `w1-fk` extra."
            ) from exc
        tensor = torch.as_tensor(qpos, dtype=torch.float32)
        matrix = chain.forward_kinematics(tensor, end_only=True).get_matrix()
        pos = matrix[:, :3, 3]
        rot_a = matrix[:, :3, 0]
        rot_b = matrix[:, :3, 1]
        return torch.cat([pos, rot_a, rot_b], dim=1).detach().cpu().numpy().astype(np.float32)


def _serial_chain(pk_module: object, chain: object, end_frame: str, root_frame: str) -> object:
    """Create a SerialChain across pytorch_kinematics argument name variants."""

    try:
        return pk_module.SerialChain(chain, end_frame_name=end_frame, root_frame_name=root_frame)
    except TypeError:
        return pk_module.SerialChain(chain, end_frame_name=end_frame, root_link_name=root_frame)
