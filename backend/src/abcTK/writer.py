"""
Base class for writing sanity predictions
"""

import os
import numpy as np
import logging
import matplotlib.pyplot as plt
import SimpleITK as sitk
from scipy import signal
#
logger= logging.getLogger(__name__)

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
        image = self.convolve_gaussian(image, axis=-1, sigma=3) ## Remove the ribs/hips!!
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
            pred = prediction[i]
            im = self.wl_norm(img[i], self.window, self.level)
            ax[i].set_title(f'Slice: {slice_nums[i]}', c='white', size=20)
            ax[i].imshow(im, cmap='gray')
            ax[i].imshow(np.where(pred == 0, np.nan, pred), cmap='plasma_r', alpha=0.5)
        output_filename = os.path.join(self.output_dir, tag +'.png')
        #output_filename = os.path.join(self.output_dir, tag + '.png')
        fig.savefig(output_filename)
        return {self.v_level: output_filename}

    def write_all_segmentation_sanity(self, tag, image, mask, filter):
        ## Filter is used to figure out what data we expect
        prediction = np.zeros_like(mask['skeletal_muscle'])

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

        for i, key in enumerate(filter.keys()):
            logger.info(f"Adding {key} to prediction")
            ## Merge predictions
            prediction += (i+1)*mask[key]

        logger.info(f"PLOTTING {tag} with mask shape: {prediction.shape}")
        img = image[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1]
        prediction = prediction[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1]

        slice_nums = np.arange(self.slice_number-self.num_slices, self.slice_number+self.num_slices+1, 1)
        for i in range(total_slices):
            pred = prediction[i]
            im = self.wl_norm(img[i], self.window, self.level)
            ax[i].set_title(f'Slice: {slice_nums[i]}', c='white', size=20)
            ax[i].imshow(im, cmap='gray')
            ax[i].imshow(np.where(pred == 0, np.nan, pred), cmap='jet', alpha=0.25)
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