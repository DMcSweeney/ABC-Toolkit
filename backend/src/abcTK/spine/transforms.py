import copy
import torch
import logging
import numpy as np
from typing import Mapping, Hashable, Dict, Tuple

from monai.config import NdarrayOrTensor, KeysCollection
from monai.transforms import Randomizable, GaussianSmooth, SpatialCrop, Resize
from monai.transforms.transform import (
    MapTransform,
    Transform
)

import SimpleITK as sitk

logger = logging.getLogger(__name__)
#** General 

class LoadDicom():
    #TODO Implement a more robust DICOM loader (monai - LoadImage pynetdicom implementation can't handle multiple series per folder?)
    def __init__(self):
        ...
    def __call__(self, data):
        ...

class Resampled(MapTransform):
    def __init__(self, keys: KeysCollection, pix_spacing: Tuple, allow_missing_keys: bool = False):
        super().__init__(keys, allow_missing_keys)
        self.pix_spacing = pix_spacing

    def __call__(self, data):
        d: Dict = dict(data)
        for key in self.key_iterator(d):
            print(key, list(d[key].meta.keys()), d[key].affine)
            d[key] = self.resample_image(d[key])
        return d
    
    def resample_image(self, Image):
        #* Resampling to isotropic grid
        resample = sitk.ResampleImageFilter()
        resample.SetInterpolator(sitk.sitkLinear)
        resample.SetOutputDirection(Image.GetDirection())
        resample.SetOutputOrigin(Image.GetOrigin())
        ratio = tuple([x/y for x, y in zip(Image.GetSpacing(), self.pix_spacing)])
        new_size = [np.round(x*s) \
            for x, s in zip(Image.GetSize(), ratio)]
        resample.SetSize(np.array(new_size, dtype='int').tolist())
        resample.SetOutputSpacing(self.pix_spacing)
        #* Ratio flipped to account for sitk.Image -> np.array transform
        return resample.Execute(Image), ratio[::-1]


#** =============== STAGE 1 =======================

class BinaryMaskd(MapTransform):
    def __init__(self, keys: KeysCollection, allow_missing_keys: bool = False):
        """
        Convert to single label - This should create the heat map for the first stage

        :param keys: The ``keys`` parameter will be used to get and set the actual data item to transform

        """
        super().__init__(keys, allow_missing_keys)

    def __call__(self, data):
        d: Dict = dict(data)
        for key in self.key_iterator(d):
            d[key][d[key] > 0] = 1
        return d

class CacheObjectd(MapTransform):
    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d: Dict = dict(data)
        for key in self.key_iterator(d):
            cache_key = f"{key}_cached"
            
            if d.get(cache_key) is None:
                d[cache_key] = copy.deepcopy(d[key])
        return d

#** =============== STAGE 2 =======================

class VertebraLocalizationSegmentation(MapTransform):
    def __init__(self, keys: KeysCollection, result: str = "result", allow_missing_keys: bool = False):
        """
        Postprocess Vertebra localization using segmentation task

        :param keys: The ``keys`` parameter will be used to get and set the actual data item to transform

        """
        super().__init__(keys, allow_missing_keys)
        self.result = result

    def _get_centroids(self, label):
        centroids = []
        # loop over all segments
        areas = []
        for seg_class in torch.unique(label):
            c = {}
            # skip background
            if seg_class == 0:
                continue

            # get centre of mass (CoM)
            centre = []
            for indices in torch.where(label == seg_class):
                # most_indices = np.percentile(indices, 60).astype(int).tolist()
                # centre.append(most_indices)
                avg_indices = np.average(indices).astype(int).tolist()
                centre.append(avg_indices)

            if len(indices) < 1000:
                continue

            areas.append(len(indices))
            c[f"label_{int(seg_class)}"] = [int(seg_class), centre[-3], centre[-2], centre[-1]]
            centroids.append(c)

        # Rules to discard centroids
        # 1/ Should we consider the distance between centroids?
        # 2/ Should we consider the area covered by the vertebra

        return centroids

    def __call__(self, data):
        d: Dict = dict(data)
        centroids = []
        for key in self.key_iterator(d):
            # Getting centroids
            centroids = self._get_centroids(d[key])
            if d.get(self.result) is None:
                d[self.result] = dict()
            d[self.result]["centroids"] = centroids
        return d

#** =============== STAGE 3 =======================

class AddCentroidFromClicks(Transform, Randomizable):
    def __init__(self, label_names, key_label="label", key_clicks="foreground", key_centroids="centroids"):
        self.label_names = label_names
        self.key_label = key_label
        self.key_clicks = key_clicks
        self.key_centroids = key_centroids

    def __call__(self, data):
        d: Dict = dict(data)

        clicks = d.get(self.key_clicks, [])
        if clicks:
            label = d.get(self.key_label, "label")
            label_idx = self.label_names.get(label, 0)
            for click in clicks:
                d[self.key_centroids] = [{f"label_{label_idx}": [label_idx, click[-3], click[-2], click[-1]]}]

        logger.info(f"Using Centroid:  {label} => {d[self.key_centroids]}")
        return d
    
class ConcatenateROId(MapTransform):
    def __init__(self, keys: KeysCollection, allow_missing_keys: bool = False):
        """
        Add Gaussian smoothed centroid (signal) to cropped volume

        :param keys: The ``keys`` parameter will be used to get and set the actual data item to transform

        """
        super().__init__(keys, allow_missing_keys)

    def __call__(self, data):
        d: Dict = dict(data)
        for key in self.key_iterator(d):
            tmp_image = np.concatenate([d["image"], d[key]], axis=0)
            d["image"] = tmp_image
        return d
    
class CropAndCreateSignald(MapTransform):
    def __init__(self, keys: KeysCollection, signal_key, allow_missing_keys: bool = False):
        """
        Based on the centroids:

        1/ Crop the image around the centroid,
        2/ Create Gaussian smoothed signal

        :param keys: The ``keys`` parameter will be used to get and set the actual data item to transform

        """
        super().__init__(keys, allow_missing_keys)
        self.signal_key = signal_key

    def __call__(self, data):
        d: Dict = dict(data)
        for key in self.key_iterator(d):
            ###########
            # Crop the image
            ###########
            d["current_label"] = list(d["centroids"][0].values())[0][-4]

            (
                x,
                y,
                z,
            ) = (
                list(d["centroids"][0].values())[0][-3],
                list(d["centroids"][0].values())[0][-2],
                list(d["centroids"][0].values())[0][-1],
            )
            current_size = d[key].shape[1:]
            original_size = d[key].meta["spatial_shape"]
            x = int(x * current_size[0] / original_size[0])
            y = int(y * current_size[1] / original_size[1])
            z = int(z * current_size[2] / original_size[2])

            # Cropping
            cropper = SpatialCrop(roi_center=[x, y, z], roi_size=(96, 96, 64))

            slices_cropped = [
                [cropper.slices[-3].start, cropper.slices[-3].stop],
                [cropper.slices[-2].start, cropper.slices[-2].stop],
                [cropper.slices[-1].start, cropper.slices[-1].stop],
            ]
            d["slices_cropped"] = slices_cropped
            d[key] = cropper(d[key])

            cropped_size = d[key].shape[1:]
            d["cropped_size"] = cropped_size

            #################################
            # Create signal based on centroid
            #################################
            signal = torch.zeros_like(d[key])
            signal[:, cropped_size[0] // 2, cropped_size[1] // 2, cropped_size[2] // 2] = 1.0

            sigma = 1.6 + (d["current_label"] - 1.0) * 0.1
            signal = GaussianSmooth(sigma)(signal)
            d[self.signal_key] = signal

        return d
    
class GetOriginalInformation(MapTransform):
    def __init__(self, keys: KeysCollection, allow_missing_keys: bool = False):
        """
        Get information from original image

        """
        super().__init__(keys, allow_missing_keys)

    def __call__(self, data):
        d: Dict = dict(data)
        for key in self.key_iterator(d):
            d["original_size"] = d[key].shape[-3], d[key].shape[-2], d[key].shape[-1]
        return d
    
class PlaceCroppedAread(MapTransform):
    def __init__(self, keys: KeysCollection, allow_missing_keys: bool = False):
        """
        Place the ROI predicted in the full image

        :param keys: The ``keys`` parameter will be used to get and set the actual data item to transform

        """
        super().__init__(keys, allow_missing_keys)

    def __call__(self, data):
        d: Dict = dict(data)
        for _ in self.key_iterator(d):
            final_pred = np.zeros(
                (1, d["original_size"][-3], d["original_size"][-2], d["original_size"][-1]), dtype=np.float32
            )
            #  Undo/invert the resize of d["pred"] #
            d["pred"] = Resize(spatial_size=d["cropped_size"], mode="nearest")(d["pred"])
            final_pred[
                :,
                d["slices_cropped"][-3][0] : d["slices_cropped"][-3][1],
                d["slices_cropped"][-2][0] : d["slices_cropped"][-2][1],
                d["slices_cropped"][-1][0] : d["slices_cropped"][-1][1],
            ] = d["pred"]
            d["pred"] = final_pred * int(d["current_label"])
        return d
