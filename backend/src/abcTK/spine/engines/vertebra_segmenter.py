import logging
from typing import Callable, Sequence

from abcTK.spine.transforms import (
    AddCentroidFromClicks,
    CacheObjectd,
    ConcatenateROId,
    CropAndCreateSignald,
    GetOriginalInformation,
    PlaceCroppedAread,
)
from monai.inferers import Inferer, SimpleInferer
from monai.transforms import (
    Activationsd,
    AsDiscreted,
    EnsureChannelFirstd,
    EnsureTyped,
    GaussianSmoothd,
    KeepLargestConnectedComponentd,
    LoadImaged,
    Resized,
    ScaleIntensityd,
    ScaleIntensityRanged,
    Spacingd,
    ToNumpyd,
)

from monailabel.interfaces.tasks.infer_v2 import InferType
from monailabel.tasks.infer.basic_infer import BasicInferTask
from monailabel.transform.post import Restored


logger = logging.getLogger(__name__)

class VertebraSegmenter(BasicInferTask):
    """
    This provides Inference Engine for pre-trained vertebra segmentation (UNet) model.
    """

    def __init__(
        self,
        path,
        network=None,
        target_spacing=(1.0, 1.0, 1.0),
        type=InferType.DEEPGROW,
        labels=None,
        dimension=3,
        description="A pre-trained model for volumetric (3D) vertebra segmentation from CT image",
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

        t = []
        add_cache = False
        if data and isinstance(data.get("image"), str):
            add_cache = True
            t.extend(
                [
                    LoadImaged(keys="image", reader="ITKReader"),
                    EnsureTyped(keys="image", device=data.get("device") if data else None),
                    EnsureChannelFirstd(keys="image"),
                    GetOriginalInformation(keys="image"),
                    AddCentroidFromClicks(label_names=self.labels),
                ]
            )

        if data and data.get("image_cached") is None:
            t.extend(
                [
                    Spacingd(keys="image", pixdim=self.target_spacing, mode="bilinear"),
                    ScaleIntensityRanged(keys="image", a_min=24 if worldmatch_correction else -1000,
                                      a_max=2924 if worldmatch_correction else 1900, b_min=0.0, b_max=1.0, clip=True),
                    GaussianSmoothd(keys="image", sigma=0.4),
                    ScaleIntensityd(keys="image", minv=-1.0, maxv=1.0),
                    CacheObjectd(keys="image"),
                ]
            )

        # Support caching for deepgrow interactions from the client
        if add_cache:
            self.add_cache_transform(t, data)

        t.extend(
            [
                CropAndCreateSignald(keys="image", signal_key="signal"),
                Resized(keys=("image", "signal"), spatial_size=self.roi_size, mode=("area", "area")),
                ConcatenateROId(keys="signal"),
            ]
        )
        return t

    def inferer(self, data=None) -> Inferer:
        return SimpleInferer()

    def post_transforms(self, data=None) -> Sequence[Callable]:
        t = [
            EnsureTyped(keys="pred", device=data.get("device") if data else None),
            Activationsd(keys="pred", softmax=True),
            AsDiscreted(keys="pred", argmax=True),
            KeepLargestConnectedComponentd(keys="pred"),
        ]

        if not data or not data.get("pipeline_mode", False):
            t.extend(
                [
                    ToNumpyd(keys="pred"),
                    PlaceCroppedAread(keys="pred"),
                    Restored(keys="pred", ref_image="image"),
                ]
            )
        else:
            t.append(Resized(keys="pred", spatial_size=data["cropped_size"], mode="nearest"))
        return t

    def writer(self, data, extension=None, dtype=None):
        if data.get("pipeline_mode", False):
            return {
                "image": data["image_cached"],
                "pred": data["pred"],
                "slices_cropped": data["slices_cropped"],
                "current_label": data["current_label"],
            }, {}

        return super().writer(data, extension, dtype)