"""
Base class for writing sanity predictions
"""

import os
import numpy as np
import logging
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import SimpleITK as sitk
from scipy import signal
#
logger= logging.getLogger(__name__)

# Fixed compartment -> integer label mapping for the combined 'ALL' sanity overlay, so a given
# compartment always gets the same color regardless of which subset of compartments happens to
# be present in a particular render, or what order they were inserted into the filter/mask dict
# (e.g. an edit-recompute can build these dicts in a different order than a full inference run).
# Covers every compartment name used across model_bank.py.
ALL_OVERLAY_COMPARTMENT_ORDER = ['body', 'skeletal_muscle', 'subcutaneous_fat', 'visceral_fat', 'IMAT']

# Explicit per-compartment color (rather than a continuous colormap like 'jet') so each tissue
# is always visually distinct and easy to tell apart during QA, regardless of which/how many
# other compartments happen to be present alongside it.
ALL_OVERLAY_COLORS = {
    'body': 'red',
    'skeletal_muscle': 'green',
    'subcutaneous_fat': 'yellow',
    'visceral_fat': 'purple',
    'IMAT': 'darkblue',
}
ALL_OVERLAY_CMAP = ListedColormap([ALL_OVERLAY_COLORS[k] for k in ALL_OVERLAY_COMPARTMENT_ORDER])
ALL_OVERLAY_NORM = BoundaryNorm(np.arange(0.5, len(ALL_OVERLAY_COMPARTMENT_ORDER) + 1.5, 1), ALL_OVERLAY_CMAP.N)

class sanityWriter():
    def __init__(self, output_dir, vertebra, slice_number, num_slices, window, level, modality, is_edit=False):
        self.output_dir = os.path.join(output_dir, 'sanity')
        if vertebra is not None:
            self.output_dir = os.path.join(self.output_dir, vertebra)
        
        if is_edit:
            self.output_dir = os.path.join(self.output_dir, 'edited')
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.v_level = vertebra
        self.slice_number = slice_number
        self.num_slices = num_slices

        self.window = window
        self.level = level
        self.modality= modality


    def write_spine_sanity(self, tag, Image,  json, loader_function):

        ## Load image
        if type(Image)==str:
            # Assume this is a path
            Image = loader_function(Image)
        
        ## Reorient
        Image, orient = self.reorient(Image, orientation='LPI')
        # Resample
        Image, ratio = self.resample_isotropic_grid(Image)
        image = sitk.GetArrayFromImage(Image)
        #image = self.convolve_gaussian(image, axis=-1, sigma=3) ## Remove the ribs/hips!!
        if self.modality in ['CT', 'CBCT']:
            mip = np.max(image, axis=-1)
        elif self.modality == 'MR':
            #mip = np.mean(image, axis=-1)
            mip = image[..., image.shape[0]//2]
        else:
            logger.error(f"Don't know how to plot modality: {self.modality}")
            raise ValueError
        ## Plot
        fig, ax = plt.subplots(1, 1, figsize=(5, 7))
        fig.patch.set_facecolor('black')
        #ax.axis('off')
        ax.imshow(mip, cmap='gray')
        ## Scale point and flip if needed
        logger.info(json)
        for vert, coords in json.items():

            loc = coords[-1]*ratio[0] ## ratio already switched to npy array indexing
            
            # Flip slice number. Slice number comes from LPS orientation but we want LPI for plotting
            loc = mip.shape[0] - loc - 1 #-1 Since size starts at 1 but indexing at 0
            if self.v_level is None:
                ax.axhline(loc, c='white', ls='--', linewidth=1)
                ax.text(0.95, loc+20, vert, c='white')
            else:
                if vert == self.v_level:
                    ax.axhline(loc, c='yellow', ls='-', linewidth=2)
                    ax.text(0.95, loc+20, vert, c='yellow')
                    ax.text(0.05, loc-20, coords[-1], c='yellow')
                else:
                    ax.axhline(loc, c='white', ls='--', linewidth=1)
                    ax.text(0.95, loc+20, vert, c='white')
        
        if self.v_level is None:
            output_filename = os.path.join(self.output_dir, tag + '.png')
        else:
            output_filename = os.path.join(self.output_dir, tag +f'-{self.v_level}.png')

        logger.info(f"Writing quality control image to {output_filename}")
        fig.savefig(output_filename)
        if self.v_level is None:
            return output_filename
        else:
            return {self.v_level: output_filename}


    def write_segmentation_sanity(self, tag, image, mask):
        prediction = mask[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1]
        img = image[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1]

        total_slices = 2*self.num_slices+1
        if total_slices == 1:
            fig, ax = plt.subplots(1, 1, figsize=(20, 5))
            ax = [ax] # To make subscriptable for plotting
        else:
            if total_slices <= 5:
                fig, ax = plt.subplots(1, total_slices, figsize=(20, 5))
            else:
                fig, axes = plt.subplots(2, total_slices//2, figsize=(20, 10))
                ax = axes.ravel()
        fig.patch.set_facecolor('black')

        slice_nums = np.arange(self.slice_number-self.num_slices, self.slice_number+self.num_slices+1, 1)
        for i in range(total_slices):
            # Binarize defensively - a mask should already be strictly 0/1, but any residual
            # fractional value (e.g. from a resample done before nearest-neighbor became the
            # default for label data) would otherwise render as a color gradient instead of a
            # single flat overlay color.
            pred = (prediction[i] > 0.5).astype(np.int8)
            im = self.wl_norm(img[i], self.window, self.level)
            ax[i].set_title(f'Slice: {slice_nums[i]}', c='white', size=20)
            ax[i].imshow(im, cmap='gray')
            ax[i].imshow(np.where(pred == 0, np.nan, pred), cmap='plasma_r', alpha=0.5)
        output_filename = os.path.join(self.output_dir, tag +'.png')
        #output_filename = os.path.join(self.output_dir, tag + '.png')
        fig.savefig(output_filename)
        return {self.v_level: output_filename}

    def write_all_segmentation_sanity(self, tag, image, mask):
        prediction = np.zeros_like(next(iter(mask.values())))

        ## Setup figure
        total_slices = 2*self.num_slices+1
        if total_slices == 1:
            fig, ax = plt.subplots(1, 1, figsize=(20, 5))
            ax = [ax] # To make subscriptable for plotting
        else:
            if total_slices <= 5:
                fig, ax = plt.subplots(1, total_slices, figsize=(20, 5))
            else:
                fig, axes = plt.subplots(2, total_slices//2, figsize=(20, 10))
                ax = axes.ravel()
        fig.patch.set_facecolor('black')

        # Fixed absolute label per compartment NAME (its index in the canonical order), not its
        # position in whatever subset of compartments this particular render happens to have -
        # otherwise a vertebra with fewer segmented tissues (e.g. T4/T9/T12, which have no fat
        # compartments) compresses e.g. IMAT down to a lower label than a vertebra with the full
        # set (e.g. L3), so the same compartment gets a different color depending on context.
        #
        # Assign (rather than sum) each pixel's label, drawing in canonical order so later/more
        # specific compartments are drawn on top. Compartments are mutually exclusive by
        # construction (single argmax over model output channels - see engine.py), so this is
        # normally a no-op disambiguation; it only matters for the rare residual overlap between
        # an edited compartment and a sibling mask that hasn't been reconciled. Summing (the
        # previous approach) would push such an overlapping pixel's value out of the intended
        # 1..len(ALL_OVERLAY_COMPARTMENT_ORDER) range entirely, rendering as an unrelated/
        # saturated color that looks like two unrelated compartments got merged together.
        for key in ALL_OVERLAY_COMPARTMENT_ORDER:
            if key not in mask:
                continue
            logger.info(f"Adding {key} to prediction")
            label = ALL_OVERLAY_COMPARTMENT_ORDER.index(key) + 1
            ## Binarize defensively - see write_segmentation_sanity.
            prediction[(mask[key] > 0.5)] = label

        logger.info(f"PLOTTING {tag} with mask shape: {prediction.shape}")
        
        ## Crop image axially around body, helps with QA (esp. of CBCT)
        nonzero = np.nonzero(prediction)
        min_x, max_x = min(nonzero[1]), max(nonzero[1])
        min_y, max_y = min(nonzero[2]), max(nonzero[2])
       

        img = image[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1, min_x-10:max_x+10, min_y-10:max_y+10]
        prediction = prediction[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1, min_x-10:max_x+10, min_y-10:max_y+10]

        slice_nums = np.arange(self.slice_number-self.num_slices, self.slice_number+self.num_slices+1, 1)
        # Discrete per-compartment color (ALL_OVERLAY_CMAP/NORM), not a continuous colormap, so
        # each tissue is always the same, clearly-distinguishable color across every slice and
        # every render, instead of matplotlib autoscaling per-subplot to whatever happens to be
        # nonzero, or two adjacent tissues (e.g. body/muscle) landing on similar-looking shades.
        for i in range(total_slices):
            pred = prediction[i]
            im = self.wl_norm(img[i], self.window, self.level)
            ax[i].set_title(f'Slice: {slice_nums[i]}', c='white', size=20)
            ax[i].imshow(im, cmap='gray')
            ax[i].imshow(np.where(pred == 0, np.nan, pred), cmap=ALL_OVERLAY_CMAP, alpha=0.4, norm=ALL_OVERLAY_NORM)
        output_filename = os.path.join(self.output_dir, tag +'.png')
        #output_filename = os.path.join(self.output_dir, tag + '.png')
        fig.savefig(output_filename)
        return {self.v_level: output_filename}


    #####################  HELPERS #############
    @staticmethod
    def wl_norm(img, window, level):
        minval = level - window/2
        maxval = level + window/2
        wld = np.clip(img, minval, maxval)
        wld -= minval
        wld /= window
        return wld
    
    @staticmethod
    def resample_isotropic_grid(Image, pix_spacing=(1, 1, 1)):
        #* Resampling to isotropic grid
        resample = sitk.ResampleImageFilter()
        resample.SetInterpolator(sitk.sitkLinear)
        resample.SetOutputDirection(Image.GetDirection())
        resample.SetOutputOrigin(Image.GetOrigin())
        ratio = tuple([x/y for x, y in zip(Image.GetSpacing(), pix_spacing)])
        new_size = [np.round(x*s) \
            for x, s in zip(Image.GetSize(), ratio)]
        resample.SetSize(np.array(new_size, dtype='int').tolist())
        resample.SetOutputSpacing(pix_spacing)
        #* Ratio flipped to account for sitk.Image -> np.array transform
        return resample.Execute(Image), ratio[::-1]

    @staticmethod
    def reorient(Image, orientation='LPS'):
        orient = sitk.DICOMOrientImageFilter()
        orient.SetDesiredCoordinateOrientation(orientation)
        return orient.Execute(Image), orient


    @staticmethod
    def convolve_gaussian(image, axis=-1, sigma=3):
        #* Convolve image with 1D gaussian  
        t = np.linspace(-10, 10, 30)
        eps = 1e-24
        gauss = np.exp(-t**2 / (2 * (sigma + eps)**2))
        gauss /= np.trapz(gauss)  # normalize the integral to 1
        kernel = gauss[None, None, :]
        logger.info(f'Kernel size: {kernel.shape}')
        return signal.fftconvolve(image, kernel, mode='same', axes=axis)