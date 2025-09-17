import time
import copy
import logging
from typing import Callable, Sequence, Dict, Tuple, Any, Union
from enum import Enum

from abcTK.spine.transforms import CacheObjectd, BinaryMaskd

from monailabel.transform.post import Restored
from monailabel.interfaces.tasks.infer_v2 import InferType
from monailabel.tasks.infer.basic_infer import BasicInferTask
from monailabel.utils.others.generic import name_to_device
from monailabel.interfaces.utils.transform import dump_data

from monai.inferers import Inferer, SlidingWindowInferer
from monai.transforms import (
    Activationsd,
    AsDiscreted,
    EnsureChannelFirstd,
    EnsureTyped,
    GaussianSmoothd,
    KeepLargestConnectedComponentd,
    LoadImaged,
    ScaleIntensityd,
    ScaleIntensityRanged,
    Spacingd,
    Orientationd
)

logger = logging.getLogger(__name__)

class CallBackTypes(str, Enum):
    PRE_TRANSFORMS = "PRE_TRANSFORMS"
    INFERER = "INFERER"
    INVERT_TRANSFORMS = "INVERT_TRANSFORMS"
    POST_TRANSFORMS = "POST_TRANSFORMS"
    WRITER = "WRITER"


class SpineFinder(BasicInferTask):
    """
    This provides Inference Engine for pre-trained spine localization (UNet) model.
    """

    def __init__(
        self,
        path,
        network=None,
        target_spacing=(1.0, 1.0, 1.0),
        type=InferType.SEGMENTATION,
        labels=None,
        dimension=3,
        description="A pre-trained model for volumetric (3D) spine localization from CT image",
        **kwargs,
    ):
        super().__init__(
            path=path,
            network=network,
            type=type,
            labels=labels,
            dimension=dimension,
            description=description,
            **kwargs,
        )
        self.target_spacing = target_spacing

    def pre_transforms(self, data=None) -> Sequence[Callable]:
        worldmatch_correction = data.get("worldmatch_correction", False)
        if worldmatch_correction:
            logger.info("Applying worldmatch correction! Intensities shifted by - 1024 HU")
        return [
            LoadImaged(keys="image", reader="ITKReader"),
            EnsureTyped(keys="image", device=data.get("device") if data else None),
            EnsureChannelFirstd(keys="image"),
            CacheObjectd(keys="image"),
            Spacingd(keys="image", pixdim=self.target_spacing),
            ScaleIntensityRanged(keys="image", a_min=24 if worldmatch_correction else -1000,
                                a_max=2924 if worldmatch_correction else 1900,
                                b_min=0.0, b_max=1.0, clip=True),
            GaussianSmoothd(keys="image", sigma=0.4),
            ScaleIntensityd(keys="image", minv=-1.0, maxv=1.0),
        ]

    def inferer(self, data=None) -> Inferer:
        return SlidingWindowInferer(
            roi_size=self.roi_size, sw_batch_size=2, overlap=0.4, padding_mode="replicate", mode="gaussian"
        )

    def post_transforms(self, data=None) -> Sequence[Callable]:
        applied_labels = list(self.labels.values()) if isinstance(self.labels, dict) else self.labels
        return [
            EnsureTyped(keys="pred", device=data.get("device") if data else None),
            Activationsd(keys="pred", softmax=True),
            AsDiscreted(keys="pred", argmax=True),
            KeepLargestConnectedComponentd(keys="pred"),
            BinaryMaskd(keys="pred"),
            Restored(keys="pred", ref_image="image"),
        ]

    def writer(self, data, extension=None, dtype=None):
        if data.get("pipeline_mode", False):
            return {"image": data["image_cached"], "pred": data["pred"]}, {}

        return super().writer(data, extension, dtype)