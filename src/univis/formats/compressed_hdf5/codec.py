"""H5FFmpeg codec profiles for dexechain-compatible HDF5 chunks."""

from __future__ import annotations

from dataclasses import dataclass

from univis.formats.compressed_hdf5.schema import GEOMAP, IMAGES, MASK


class HDF5VideoCodec:
    """Interface for HDF5 video dataset creation options."""

    def dataset_kwargs(self, modality: str) -> dict:
        """Return h5py `create_dataset` kwargs for one video modality."""

        raise NotImplementedError


@dataclass(frozen=True)
class DexH5FFmpegCodec(HDF5VideoCodec):
    """Dexechain h5ffmpeg profile without importing dexechain."""

    use_nvenc_for_video: bool = False

    @classmethod
    def from_environment(cls) -> "DexH5FFmpegCodec":
        """Select the dexechain CUDA profile when torch reports RTX 3060."""

        try:
            import torch

            name = torch.cuda.get_device_name()
        except Exception:
            return cls(use_nvenc_for_video=False)
        return cls(use_nvenc_for_video=("3060" in name))

    def dataset_kwargs(self, modality: str) -> dict:
        """Return dexechain-equivalent h5ffmpeg compression kwargs."""

        import h5ffmpeg as hf

        if modality == MASK:
            return hf.x264(preset="veryslow", tune="ssim", crf=0)
        if modality in {IMAGES, GEOMAP} and self.use_nvenc_for_video:
            return hf.h264_nvenc()
        if modality in {IMAGES, GEOMAP}:
            return hf.x264(preset="veryfast", tune="fastdecode")
        raise KeyError(f"unsupported compressed HDF5 modality: {modality}")
