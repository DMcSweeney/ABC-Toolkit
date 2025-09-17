"""
Base class for segmentation engine 
"""

import os
import ast
import time
import logging
import SimpleITK as sitk
import numpy as np
from scipy import signal
import pydicom

import torch
import onnx
import onnxruntime as ort
import albumentations as A

from albumentations.pytorch.transforms import ToTensorV2
from monai.transforms.spatial.functional import resize
from scipy.special import softmax
import skimage
from scipy.ndimage import binary_dilation, generate_binary_structure
from flask import abort
from rt_utils import RTStructBuilder

from abcTK.writer import sanityWriter
from abcTK.wrapper import ONNXInferenceWrapper

logger = logging.getLogger(__name__)

class segmentationEngine():
    def __init__(self, output_dir, modality, vertebra, worldmatch_correction, fat_threshold=(-190, -30), muscle_threshold=(-29, 150), series_uuid=None,
                 model_bank=None, **kwargs):
        self.output_dir = output_dir
        self.modality = modality
        self.v_level = vertebra
        self.series_uuid = series_uuid

        
        self.worldmatch_correction = worldmatch_correction  ## If data has gone through worldmatch need to shift intensities by -1024

        self.thresholds = {
            'skeletal_muscle': muscle_threshold,
            'subcutaneous_fat': fat_threshold,
            'IMAT': fat_threshold,
            'visceral_fat': fat_threshold,
            'body': (None, None) # No thresholds for body mask
        }

        self._init_model_bank(model_bank) #* Load bank of models
        #self._set_options() #* Set ONNX session options

        #self.ort_session = ort.InferenceSession(self.model_paths[modality], sess_options=self.sess_options)
        onnx_model = onnx.load(self.model_paths[modality]['path'])
        self.ort_session = ONNXInferenceWrapper(self.model_paths[modality]['path'], onnx_model)
        
        self.segment_dict = self.model_paths[modality]['segments']
        self.segments = [x for x in self.segment_dict.keys()]


        #* ImageNet pre-processing transforms
        self.transforms = A.Compose([
            A.Resize(512, 512),
            A.Normalize(mean=(0.485, 0.456, 0.406), 
            std=(0.229, 0.224, 0.225), max_pixel_value=1),
            ToTensorV2()
            ],)
    
    
    def forward(self, input_path, slice_number, num_slices, loader_function, generate_bone_mask, **kwargs):
        ###* ++++++++++ PRE-PROCESS +++++++++++++++++
        self.loader_function = loader_function ## TO re-use in plotting.
        mask_dir = os.path.join(self.output_dir, 'masks')
        os.makedirs(mask_dir, exist_ok=True)
        start = time.time()
        
        #Reorient, resample, calc. slice number 
        origImage, Image, image = self.load_data(input_path, generate_bone_mask, mask_dir, slice_number, **kwargs)

        #* Create some holders to put predictions
        #TODO Should predictions be written to disk? Slower but less mem. w/ big input res.
        holder = np.zeros_like(image, dtype=np.int8)
        self.holders = { x: holder.copy() for x in self.segments}

        #* Subset the reference image
        self.num_slices = num_slices
        self.img = self.prepare_multi_slice(image)

        pre_processing_time = time.time() - start
        logger.info(f"Pre-processing: {pre_processing_time} s")

        ###* ++++++++++ INFERENCE +++++++++++++++++
        #TODO This can be parallelised
        logger.info(f"==== INFERENCE ====")
        start = time.time()
        for i in range(self.img.shape[0]):
            self.per_slice_inference(i)

        inference_time = time.time() - start
        logger.info(f"Total inference: {inference_time} s")

        ###* ++++++++++ POST-PROCESS +++++++++++++++++
        start = time.time()
        ## Extracts IMAT
        if 'skeletal_muscle' in self.holders:
            self.extract_imat(image)
        
        #TODO IF a mask exists, read it, overwrite and save!! That way all levels will be annotated in the same file.
        output = self.post_process(mask_dir, Image, origImage, compartment=None, **kwargs) # Returns stats for every compartment at every slice
        post_processing_time = time.time() - start
        logger.info(f"Post-processing: {post_processing_time} s")
        return output 


    def forward_extract_stats(self, input_path, mask_path, loader_function, generate_bone_mask, compartment, **kwargs):
        #* Method for re-extracting stats from a mask provided in the request
        #* Model inference is not performed! I.e. the mask should exist ahead of time.
        self.loader_function = loader_function
        self.settings = self._get_window_level()
        mask_dir = os.path.join(self.output_dir, 'masks')
        assert os.path.isdir(mask_dir)

        origImage, Image, image = self.load_data(input_path, generate_bone_mask, mask_dir, slice_number=None)
        
        ## Get the loader function for the mask
        mask_loader, mask_loader_name = self.get_mask_loader_function(mask_path)
        Mask = mask_loader(mask_path)
        resampler = sitk.ResampleImageFilter()
        resampler.SetReferenceImage(Image)
        Mask = resampler.Execute(Mask)
        mask = sitk.GetArrayFromImage(Mask)
        
        ## BINARY DILATION TO DEAL WITH SLICER3D EXPORT BULLSHIT
        #TODO this probably shouldn't be here!
        if 'dilate_mask' in kwargs and kwargs['dilate_mask']:
            # Only dilate mask in-plane
            struct_size = 3
            struct = np.ones((struct_size, struct_size), bool)[None] ## Shape: 1 x struct size x struct size
            mask = binary_dilation(mask, structure=struct).astype(mask.dtype)

        self.slice_number, self.num_slices = self.get_slices_of_interest_from_mask(mask)
        logger.info(f"Slice number: {self.slice_number}. Num slices: {self.num_slices}")
        self.holders = {}
        if compartment == 'total_muscle':
            self.holders['skeletal_muscle'] = mask
            self.extract_imat(image)
            # Rename to deal with post-processing
            compartment = 'skeletal_muscle' 

        output = self.post_process(mask_dir, Image, origImage, compartment, **kwargs)
       
        return output

    ###############################################
    #* ================ HELPERS ==================
    ###############################################


    def load_data(self, input_path, generate_bone_mask, mask_dir, slice_number, **kwargs):
        #* Load input volume
        origImage = self.loader_function(input_path) # Returns SimpleITK image and reference slice
        
        if 'resample' in kwargs and kwargs['resample']:
            if 'resample_spacing' in kwargs:
                logger.info(f"Resampling image (shape: {origImage.GetSize()}) from spacing {origImage.GetSpacing()} to {kwargs['resample_spacing']}")
                origImage, ratio = self.resample_image(origImage, output_spacing=kwargs['resample_spacing'])
                if slice_number is not None:
                    slice_number = slice_number * ratio[-1]

                logger.info(f"Resampled image shape: {origImage.GetSize()}")
            elif 'resample_transform' in kwargs:
                #Resample given path to DICOM registration object
                logger.info(f"Reading transform from file: {kwargs['resample_transform']}")
                # Read transform and convert to sitk Transform
                Transform = self.read_transform(origImage, kwargs['resample_transform'])
                
                # Load the reference scan or get info from db.
                if os.path.isfile(kwargs['reference_scan']) or os.path.isdir(kwargs['reference_scan']):
                    # If file or directory, use loader function to read
                    logger.info(f"Trying to read reference_scan from disk using: {self.loader_function}")
                    referenceImage = self.loader_function(kwargs['reference_scan'])
                    reference_info = {'Origin': referenceImage.GetOrigin(), 'Spacing': referenceImage.GetSpacing(),
                                       'Direction': referenceImage.GetDirection(), 'Size': referenceImage.GetSize()}
                else:
                    logger.info(f"Assuming reference_scan ({kwargs['reference_scan']}) specifies an _id in the database")
                    from app import mongo

                    query = mongo.db.images.find_one({"_id": kwargs['reference_scan']})
                    reference_info = {'Origin': ast.literal_eval(query['origin']), 'Spacing': ast.literal_eval(query['spacing']),
                    'Direction': ast.literal_eval(query['direction']), 'Size': ast.literal_eval(query['size'])}
                
                logger.info(f"Found info for the reference scan: {reference_info}")
                logger.warning(f"Applying transform. This will resample and pad to match the reference scan (specified by reference_scan arg.)")
                origImage = self.apply_transform(origImage, Transform, reference_info)
            elif 'reference_scan' in kwargs and all([x not in kwargs for x in ['resample_spacing', 'resample_transform']]):
                # If resampling requested and a reference scan provided, but no transform.
                logger.info(f"Resampling to reference scam: {kwargs['reference_scan']}")
                # Load the reference scan or get info from db.
                if os.path.isfile(kwargs['reference_scan']) or os.path.isdir(kwargs['reference_scan']):
                    # If file or directory, use loader function to read
                    logger.info(f"Trying to read reference_scan from disk using: {self.loader_function}")
                    referenceImage = self.loader_function(kwargs['reference_scan'])
                    reference_info = {'Origin': referenceImage.GetOrigin(), 'Spacing': referenceImage.GetSpacing(),
                                       'Direction': referenceImage.GetDirection(), 'Size': referenceImage.GetSize()}
                else:
                    logger.info(f"Assuming reference_scan ({kwargs['reference_scan']}) specifies an _id in the database")
                    from app import mongo

                    query = mongo.db.images.find_one({"_id": kwargs['reference_scan']})
                    reference_info = {'Origin': ast.literal_eval(query['origin']), 'Spacing': ast.literal_eval(query['spacing']),
                    'Direction': ast.literal_eval(query['direction']), 'Size': ast.literal_eval(query['size'])}
                origImage = self.resample_to_reference(origImage, reference_info)

        if 'calibrate_cbct' in kwargs:
            ## Query database for reference scan and get RTSTRUCT
            from app import mongo
            query = mongo.db.images.find_one({"_id": kwargs['reference_scan']})

            if 'rtstruct_path' not in query:
                logger.error('No path to RTSTRUCT')
                raise ValueError('No path to RTSTRUCT')
            
            logger.info(f"Loading RTSTRUCT from {query['rtstruct_path']}")
            assert os.path.isfile(query['rtstruct_path']), "Cannot read RTSTRUCT"
            rtstruct = RTStructBuilder.create_from(dicom_series_path=query['input_path'], rt_struct_path=query['rtstruct_path'])
            matching_structures = [x for x in rtstruct.get_roi_names() if kwargs['calibration_structure'] == x.lower()]
            if not matching_structures:
                logger.error(f"Structure {kwargs['calibration_structure']} not found in RTSTRUCT ({rtstruct.get_roi_names()})")
                raise ValueError
            if len(matching_structures) > 1:
                logger.error(f"Too many structures found matching: {kwargs['calibration_structure']} ({rtstruct.get_roi_names()})")
                raise ValueError
            # Load mask
            mask = rtstruct.get_roi_mask_by_name(matching_structures[0])
            mask = np.moveaxis(mask, -1, 0).astype(float)#
            # Load reference scan
            from abcTK.inference.segment import get_loader_function
            pCT_loader, _ = get_loader_function(query['input_path'])
            pCT = pCT_loader(query['input_path'])
            ## Do the calibration
            pCT_values = self.get_intensities_for_calibration(pCT, mask)
            CBCT_values = self.get_intensities_for_calibration(origImage, mask)
            calibration = []
            for idx, val in pCT_values.items():
                if idx not in CBCT_values:
                    continue
                ## Apply a shift prior to calibration, otherwise issues when near 0
                logger.info(f"Raw values at index {idx} (PCT/CBCT): {val}/{CBCT_values[idx]}")
                val += 1024
                CBCT_values[idx] += 1024
                
                if int(CBCT_values[idx]) == 0:
                    logger.warning(f"CBCT intensity at index {idx} is 0, not accounting for in calibration")
                    continue
                else:
                    logger.info(f"Shifted values at index {idx} (PCT/CBCT): {val}/{CBCT_values[idx]}")
                    calib = val/CBCT_values[idx]
                    logger.info(f"Calibration factor: {calib}")
                    calibration.append(calib)
            
            ## Get the scaling factor
            kwargs['scale_intensity'] = np.nanmean(calibration)
            
            logger.info(f'Extracted calibration, will apply scaling factor: {kwargs["scale_intensity"]}')
            ## Plot calibration 
        
        
        Image, orient = self.reorient(origImage, orientation='LPS')
        #* Flip the slice number if the image was flipped
        if orient.GetFlipAxes()[-1] and slice_number is not None:
            logger.info(f"Original slice number: {slice_number}")
            slice_number = Image.GetSize()[-1] - int(slice_number) - 1 # Since size starts at 1 but indexing starts at 0
            logger.info(f'New slice number: {slice_number}')
        
        self.slice_number = slice_number

        if type(Image) == np.array:
            image = Image
            pixel_spacing = (1, 1, 1)
        else:
            image = sitk.GetArrayFromImage(Image)
            pixel_spacing = Image.GetSpacing()

        if 'shift_intensity' in kwargs:
            logger.info(f"Shifting intensity by: {kwargs['shift_intensity']}")
            image = image + kwargs['shift_intensity'] 

        if 'scale_intensity' in kwargs:
            logger.info(f"Scaling intensity by: {kwargs['scale_intensity']}")
            image = image * kwargs['scale_intensity'] 
    
        if self.worldmatch_correction:
            image -= 1024

        self.image = image.copy()
        ##* Load the bone mask or generate
        if type(generate_bone_mask) == bool and generate_bone_mask:
            # Regenerat
            logger.info("Generating bone mask")
            Bone = self.generate_bone_mask_CT(Image, pixel_spacing)
            sitk.WriteImage(Bone, os.path.join(mask_dir, 'BONE.nii.gz'))
            Bone, _ = self.reorient(Bone, orientation='LPS')
            self.bone = sitk.GetArrayFromImage(Bone)
            self.bone = np.logical_not(self.bone)

        elif type(generate_bone_mask) == str:
            # Assume this is a path
            logger.info(f"Reading bone mask from file: {generate_bone_mask}")
            Bone = sitk.ReadImage(generate_bone_mask)
            Bone, _ = self.reorient(Bone, orientation='LPS')
            self.bone = sitk.GetArrayFromImage(Bone)
            self.bone = np.logical_not(self.bone)
        else:
            self.bone = None

        ## Return the original SimpleITK Image, the reoriented/resampled SimpleITK Image and the numpy array image
        return origImage, Image, image

    def generate_bone_mask_CT(self, Image, pixel_spacing, threshold = 350, radius = 3):
        #~ Create bone mask (by thresholding) for handling partial volume effect
        #@threshold in HU; radius in mm.
        logger.info(f"Generating bone mask using threshold ({threshold}) and expanding isotropically by {radius} mm")
        #* Apply threshold
        bin_filt = sitk.BinaryThresholdImageFilter()
        bin_filt.SetOutsideValue(1)
        bin_filt.SetInsideValue(0)

        if self.worldmatch_correction:
            bin_filt.SetLowerThreshold(0)
            bin_filt.SetUpperThreshold(threshold+1024)
        else:
            bin_filt.SetLowerThreshold(-1024)
            bin_filt.SetUpperThreshold(threshold)

        bone_mask = bin_filt.Execute(Image)
        
        #* Convert to pixels
        pix_rad = [int(radius//elem) for elem in pixel_spacing]
        
        #* Dilate mask
        dil = sitk.BinaryDilateImageFilter()
        dil.SetKernelType(sitk.sitkBall)
        dil.SetKernelRadius(pix_rad)
        dil.SetForegroundValue(1)
        Bone= dil.Execute(bone_mask)
        return sitk.Cast(Bone, sitk.sitkInt8)
    
    def prepare_multi_slice(self, image):
        """
        This prepares multi-slice inputs and maintains slice # to index mapping.
        i.e. Batch size = 2*num_slices + 1  
        """
        self.idx2slice = {}
        logger.info(f"Pre-processing input slices (# slices: {self.num_slices*2 +1})")
        for i, slice_ in enumerate( np.arange(self.slice_number- self.num_slices, self.slice_number+self.num_slices+1) ):
            im_tensor = self.pre_process(image, slice_)

            if im_tensor is None:
                logger.warn(f"The selected slice ({slice_}) is out of range - skipping.")
                continue

            if i == 0:
                img = im_tensor[None]
            else:
                img = torch.cat([img, im_tensor[None]], axis=0)
            self.idx2slice[i] = slice_

        return np.array(img)
    
    def pre_process(self, image, slice_number):
        #* Pre-processing
        try:
            im = image[slice_number]
        except IndexError: #* Slice out of bounds
            return None

        self.settings = self._get_window_level()
        logger.info(f"Window/Level ({self.settings['window']}/{self.settings['level']}) normalisation")
        im = self.wl_norm(im, window=self.settings['window'], level=self.settings['level'])
        
        logger.info(f"Converting input to three channels")
        im = self.expand(im) #* 3 channels
        logger.info(f"Applying transforms: {self.transforms}")
        augmented = self.transforms(image=im)
        return augmented['image']
    
    def remove_bone(self, i, pred):
        # Resize to match prediction/input
        bone_mask = self.bone[self.idx2slice[i]]
        return np.logical_and(pred, bone_mask)   

    def per_slice_inference(self, i):
        input = self.img[[i]] 
        is_divisible = [x % 2 == 0 for x in input.shape[-2:] ]
        is_too_small = [x < 256 for x in input.shape[-2:]]
        if not all(is_divisible) or all(is_too_small):
            #TODO Resampling will affect measurements, if new pixel size not used for calc.
            logger.error(f"Issues with input shape: {input.shape}, resampling not yet implemented.")
            return None, None, None
            #input = resize(input, (512, 512), mode='bicubic')
        prediction = self.inference(input)

        logger.info(f"Updating holders (shape: {prediction.shape}) into compartments.")

        for compartment, channel in self.segment_dict.items():
            pred = prediction[channel]
            self.holders[compartment][self.idx2slice[i]] = self.remove_bone(i, pred) if self.bone is not None else pred

    def inference(self, img):
        #* Forward pass through the model
        t= time.time()
        ort_inputs = {self.ort_session.get_inputs()[0].name: \
            img.astype(np.float32)}
        logger.info(f'Model load time (s): {np.round(time.time() - t, 7)}')
        #* Inference
        t= time.time()
        outputs = np.array(self.ort_session.run(None, ort_inputs)[0])
        outputs = np.squeeze(outputs)
        logger.info(f'Inference time (s): {np.round(time.time() - t, 7)}')
        logger.info(f"Model outputs: {outputs.shape}")

        if outputs.shape[0] > 1:
            logger.info("Multiple channels detected, applying softmax")
            pred = np.argmax(softmax(outputs, axis=0), axis=0).astype(np.int8) # Argmax then one-hot encode
            preds = [np.where(pred == val, 1, 0) for val in np.unique(pred)] # one-hot encode
            return np.stack(preds)
        else:
            logger.info("Single channel detected, applying sigmoid")
            return np.round(self.sigmoid(outputs)).astype(np.int8)

    def post_process(self, mask_dir, refImage, originalImage, compartment, **kwargs):
        output_mask_dir = os.path.join(mask_dir, self.v_level)
        os.makedirs(output_mask_dir, exist_ok=True)

        if "is_edit" in kwargs:
            is_edit = kwargs['is_edit']
        else:
            is_edit = False

        writer = sanityWriter(self.output_dir, self.v_level, self.slice_number, self.num_slices, self.settings['window'], self.settings['level'], self.modality, is_edit)

        data = {}
        paths_to_sanity = {}
        if compartment is None:
            compartments = self.segments
        else:
            compartments = [compartment]

        for compartment in compartments:
            logger.info(f"Analysing compartment: {compartment}")
            
            if compartment == 'background': continue # Skip background

            if compartment == 'skeletal_muscle' and 'IMAT' not in self.segments:
                    if not all([x is None for x in self.thresholds['IMAT']]):
                        logger.info("Extracting IMAT stats")
                        data['IMAT'] = self.extract_stats(self.holders['IMAT'], self.thresholds['IMAT'])

                        logger.info("Writing IMAT sanity check")
                        paths_to_sanity['IMAT'] = writer.write_segmentation_sanity('IMAT', self.image, self.holders['IMAT'])
                        #* Convert predictions back to ITK Image, using input Image as reference
                        logger.info(f"Converting IMAT mask to ITK Image. Size: {self.holders['IMAT'].shape}")
                        IMAT  = self.npy2itk(self.holders['IMAT'] , refImage)
                        logger.info("Writing IMAT mask")
                        self.save_prediction(output_mask_dir, 'IMAT', IMAT, originalImage)

                        logger.info("Removing IMAT from skeletal_muscle")
                        self.holders['skeletal_muscle'] = np.where(self.holders['IMAT'] == 1, 0, self.holders['skeletal_muscle']).astype(np.int8)
                    else:
                        logger.warning("NOT CALCULATING IMAT - NO FAT THRESHOLDS PROVIDED.")
            
            data[compartment] = self.extract_stats(self.holders[compartment], self.thresholds[compartment])
            logger.info(f"Writing {compartment} sanity check")
            paths_to_sanity[compartment] =writer.write_segmentation_sanity(compartment, self.image, self.holders[compartment])
            logger.info(f"Converting {compartment} to ITK Image. Size: {self.holders[compartment].shape}")
            SkeletalMuscle = self.npy2itk(self.holders[compartment], refImage)
            logger.info(f"Writing {compartment} mask")
            self.save_prediction(output_mask_dir, compartment, SkeletalMuscle, originalImage)
        
        if 'override_spine_sanity' in kwargs:
            json = {self.v_level: [0, 0, self.slice_number]}
            paths_to_sanity['SPINE'] = writer.write_spine_sanity('SPINE', originalImage, json, self.loader_function)
        else:
            ## Check if labelling has been done else plot spine
            from app import mongo
            database = mongo.db
            res = database.images.find_one({"_id": self.series_uuid}, {"labelling_done": 1})
            if res is not None:
                if res['labelling_done'] == 'False':
                    json = {self.v_level: [0, 0, self.slice_number]}
                    paths_to_sanity['SPINE'] = writer.write_spine_sanity('SPINE', originalImage, json, self.loader_function)
                else:
                    json = database.spine.find_one({"_id": self.series_uuid}, {"prediction": 1})
                    paths_to_sanity['SPINE'] = writer.write_spine_sanity('SPINE', originalImage, json['prediction'], self.loader_function)

        paths_to_sanity['ALL'] = writer.write_all_segmentation_sanity('ALL', self.image, self.holders, data)
        return data, paths_to_sanity

    def extract_stats(self, mask, thresholds):
        #* Extract region of interest
        prediction = mask[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1]
        image = self.image[self.slice_number-self.num_slices:self.slice_number+self.num_slices+1]
        logger.info(f"Extracting stats from sub-volume with shape: {image.shape}")
        logger.info(f"Applying thresholds: {thresholds}")
        #* Apply thresholding
        threshold_image = self.threshold_mask(image, thresholds)
        prediction = np.logical_and(threshold_image, prediction).astype(np.int8)

        #* Calculate stats across subset
        stats = {}
        slice_numbers = [x for x in np.arange(self.slice_number-self.num_slices, self.slice_number+self.num_slices+1) ]

        for idx, slice_num in zip(range(image.shape[0]), slice_numbers) :
            im, pred = image[idx], prediction[idx]
            #* Area calculation          
            area = float(np.sum(pred))
            #* Density calculation
            density = float(np.mean(im[pred==1]))
            stats[f'Slice {slice_num}'] = {'area (voxels)': area, 'density (HU)': density}
        
        return stats

    def extract_imat(self, numpyImage):
        # Extract IMAT from muscle segmentation: fatByThreshold U muscleSegmentation
        logger.info(f"Generating IMAT mask using thresholds: {self.thresholds['IMAT']}")

        #TODO Make this faster!! This seems to be relatively slow (~1sec)
        blurred_image = self.convolve_gaussian(numpyImage, axis=None, sigma=0.5)
        fat_threshold = self.threshold_mask(blurred_image, self.thresholds['IMAT'])
        
        IMAT = np.logical_and(fat_threshold, self.holders['skeletal_muscle']).astype(np.int8)
        connected_components = skimage.measure.label(IMAT, connectivity=2, return_num=False) # connected components
        # Each component is assigned a diff. label so need to cast to 1
        self.holders['IMAT'] = np.where(connected_components != 0, 1, 0)

    def save_prediction(self, output_dir, tag, Prediction, origImage):
        #* Save mask to outputs folder
        output_filename = os.path.join(output_dir, tag + '.nii.gz')
        
        # Resample Prediction to origImage
        Prediction = sitk.Resample(Prediction, origImage, sitk.Transform(), sitk.sitkLinear, 0, origImage.GetPixelID())
        logger.info(f"Saving prediction with shape {Prediction.GetSize()} to: {output_filename}")

        sitk.WriteImage(Prediction, output_filename)
    
    def threshold_mask(self, image, thresholds):
        if thresholds[0] is None:
            logger.info("No lower threshold")
            lower_threshold = image.min()
        else:
            lower_threshold = thresholds[0]
        if thresholds[1] is None:
            logger.info("No upper threshold")
            upper_threshold = image.max()
        else:
            upper_threshold = thresholds[1]
        return np.logical_and(image >= lower_threshold ,image <= upper_threshold).astype(np.int8)


    ###########################################################
    #* =================== STATIC METHODS =====================
    ############################################################
    @staticmethod
    def wl_norm(img, window, level):
        if window is None:
            window = img.max()-img.min()
        if level is None:
            level = img.mean()
        minval = level - window/2
        maxval = level + window/2
        wld = np.clip(img, minval, maxval)
        wld -= minval
        wld /= window
        return wld

    @staticmethod
    def expand(img):
        #* Convert to 3 channels
        return np.repeat(img[..., None], 3, axis=-1)
    
    @staticmethod
    def npy2itk(npy, reference):
        #* npy array to itk image with information from reference
        Image = sitk.GetImageFromArray(npy)
        Image.CopyInformation(reference)
        return Image

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
        kernel = gauss[None, None, :]*gauss[:, None, None]*gauss[None, :, None]
        logger.info(f"Kernel size: {kernel.shape}")
        return signal.fftconvolve(image, kernel, mode='same', axes=axis)

    @staticmethod
    def get_mask_loader_function(path):
        # Accepts numpy and nifty masks.
        #TODO add support for RTSTRUCTs
        def load_numpy(path):
            img = np.load(path)
            return sitk.GetImageFromArray(img)

        def load_nifty(path):
            #* Read nii volume
            return sitk.ReadImage(path)

        def load_nrrd(path):
            return sitk.ReadImage(path)

        assert os.path.isfile(path), f"{path} is not a file. We assume your mask is saved as a file... maybe we should relax this?"

        # If file, check extension.
        ext = os.path.splitext(path)[-1]
        # Handle .nii.gz
        if ext == '.gz':
            split = path.rstrip('.gz').split(".")[-1]
            if split == 'nii':
                ext = '.nii.gz'
            elif split == 'nrrd':
                ext = '.nrrd.gz'
            else:
                logger.warning(f"Unrecognized file extension: {path}")
        
        logger.warning(f"Input file extension: {ext}")
        if ext in ['.nii', '.nii.gz']:
            return load_nifty, 'nifty'
        elif ext in ['.npy', '.npz']:
            return load_numpy, 'numpy'
        elif ext in ['.nrrd', '.nrrd.gz']:
            return load_nrrd, 'nrrd'
        
    @staticmethod
    def get_slices_of_interest_from_mask(mask):
        #* Given a mask, extracts the median slice number and the number of slices either side
        # Mask shape should be H x W x D 
        roi = list(np.sum(mask, axis=(1, 2)))
        
        idc = [i for i in range(len(roi)) if roi[i]>0]
        logger.info(f"Found {len(idc)} slices with a mask.")
        if len(idc) == 2:
            logger.warn(f"Only detected two slices with mask! Using the first index (Slice {idc[0]}) as central slice and assuming num_slices == 1")
            return int(idc[0]), 1
        elif len(idc) == 0:
            raise ValueError("No mask found!")

        assert len(idc) % 2 != 0, "Number of slices is even, can't handle that atm.."

        return int(np.median(idc)), (len(idc)-1)//2

    @staticmethod
    def resample_image(Image, output_spacing):
        #TODO Add ability to resample given a transform 
        resample = sitk.ResampleImageFilter()
        resample.SetInterpolator(sitk.sitkLinear)
        resample.SetOutputDirection(Image.GetDirection())
        resample.SetOutputOrigin(Image.GetOrigin())
        ratio = tuple([x/y for x, y in zip(Image.GetSpacing(), output_spacing)])
        new_size = [np.round(x*s) for x, s in zip(Image.GetSize(), ratio)]
        resample.SetSize(np.array(new_size, dtype='int').tolist())
        resample.SetOutputSpacing(output_spacing)
        return resample.Execute(Image), ratio
    
    @staticmethod
    def resample_to_reference(Image, referenceInfo):
        resample = sitk.ResampleImageFilter()
        resample.SetInterpolator(sitk.sitkLinear)
        resample.SetOutputDirection(referenceInfo['Direction'])
        resample.SetOutputOrigin(referenceInfo['Origin'] )
        resample.SetSize(referenceInfo['Size'])
        resample.SetOutputSpacing(referenceInfo['Spacing'])
        resample.SetDefaultPixelValue(-1024)
        return resample.Execute(Image)


    @staticmethod
    def read_transform(Image, transform_file):
        assert os.path.isfile(transform_file), f"Transform file ({transform_file}) does not exist."

        ## Read transform
        ds = pydicom.dcmread(transform_file)
        transforms = []
        for elem in ds.RegistrationSequence:
            for reg_seq in elem.MatrixRegistrationSequence:
                for seq in reg_seq.MatrixSequence:
                    reg_type =  seq[0x0070, 0x030c].value # RIGID
                    matrix = seq[0x3006, 0x00c6].value # TRANSFORM MATRIX
                    transforms.append({"type": reg_type, "matrix": matrix})
                ##TODO this is here to catch Elekta SROs that have three transforms: identity (why??), planned shift & rotations and as-treated couch shifts
                ## As is, code skips the final transform (as treated) because it is the second element of reg_seq.MatrixSequence 
                break 
        
        Transform = sitk.CompositeTransform(3)
        for step in transforms[::-1]: # Invert list - listed in DICOM SRO in order to apply them. SimpleITK expects the reverse (first provided = last applied)
            if step['type'] == 'RIGID':
                # Define sitk transform
                matrix = np.array(step['matrix']).reshape((4, 4))
                affine = sitk.AffineTransform(3)
                affine.SetMatrix(matrix[:3, :3].ravel())
                affine.SetTranslation(matrix[:, -1].ravel())
                affine.SetCenter(Image.TransformContinuousIndexToPhysicalPoint(np.array(Image.GetSize()) / 2.0)) # Center of rotation
                Transform.AddTransform(affine)
            else:
                raise ValueError(f"Don't know how to apply registration type: {step['type']}")

        return Transform
    
    @staticmethod
    def apply_transform(Image, transform, reference_info):
        ## reference info should be dict with: 
        # Spacing, Origin, Direction, Size

        def transform_moving_onto_fixed(Image, transform, output_spacing):
            ### Assumes transform maps the CBCT onto the planning CT (i.e. moving onto fixed)
            # 1. Get the extreme points of the moving volume
            extreme_points = [
                            Image.TransformIndexToPhysicalPoint((0, 0, 0)),
                            Image.TransformIndexToPhysicalPoint((Image.GetWidth(), 0, 0)),
                            Image.TransformIndexToPhysicalPoint((0, Image.GetHeight(), 0)),
                            Image.TransformIndexToPhysicalPoint((0, 0, Image.GetDepth())),
                            Image.TransformIndexToPhysicalPoint((Image.GetWidth(), Image.GetHeight(), 0)),
                            Image.TransformIndexToPhysicalPoint((Image.GetWidth(), 0, Image.GetDepth())),
                            Image.TransformIndexToPhysicalPoint((0, Image.GetHeight(), Image.GetDepth())),
                            Image.TransformIndexToPhysicalPoint((Image.GetWidth(), Image.GetHeight(), Image.GetDepth())),
                        ]
            #2. Apply transform to those points
            extreme_points_transformed = [transform.TransformPoint(pt) for pt in extreme_points]

            #3. Figure out the new extreme points in each dim
            min_x = min(extreme_points_transformed)[0]
            min_y = min(extreme_points_transformed, key=lambda p: p[1])[1]
            min_z = min(extreme_points_transformed, key=lambda p: p[2])[2]
            max_x = max(extreme_points_transformed)[0]
            max_y = max(extreme_points_transformed, key=lambda p: p[1])[1]
            max_z = max(extreme_points_transformed, key=lambda p: p[2])[2]

            #4. Set remaining vars.
            output_direction = Image.GetDirection() #transform.GetMatrix()
            output_origin = transform.TransformPoint(Image.GetOrigin())
            output_spacing = [float(x) for x in output_spacing] # COnvert from str to float
            output_size = [int((max_x - min_x) / output_spacing[0]), int((max_y - min_y) / output_spacing[1]), int((max_z - min_z) / output_spacing[2])]

            Image = sitk.Resample(
                Image, output_size, transform.GetInverse(), sitk.sitkLinear, output_origin, output_spacing, output_direction, -1024, Image.GetPixelID()
            )
            return Image

        def pad_moving_onto_fixed(Image, output_size, output_origin):
            ## Pad so that sizes match
            output_spacing = Image.GetSpacing()
            output_direction = Image.GetDirection()

            Image = sitk.Resample(
                Image, output_size, sitk.Transform(), sitk.sitkLinear, output_origin, output_spacing, output_direction, -1024, Image.GetPixelID()
                )

            return Image 
        
        Image = transform_moving_onto_fixed(Image, transform, reference_info['Spacing'])
        Image = pad_moving_onto_fixed(Image, reference_info['Size'], reference_info['Origin'])

        return Image

    @staticmethod
    def get_intensities_for_calibration(Image, mask):
        ## Get mean intensity within mask at every slice
        ## Image should be sitk.Image and mask np.array
        image = sitk.GetArrayFromImage(Image)
           # Figure out indices with mask 
        idc = np.asarray(np.max(mask, axis=(1, 2)) == 1).nonzero()[0]
        # Find the slice of interest (bottom slice + reference point) (i.e. Center of mass in Z)
        data = {}  
        for idx in idc:
            val = image[idx][mask[idx] == 1].mean() + 1024 #!! +1024 needed to shift 0 reduces effect of noise on calibration. E.g. -1/50 -> 1023/1074
            data[idx] = val
            
        return data

    #####################################################
    #*  ================= OPTIONS ==================
    #####################################################
    def _init_model_bank(self, model_bank=None):
        #* Paths to segmentation models
        if model_bank is None:
            from abcTK.segment.model_bank import model_bank 
        
        if self.v_level in model_bank:
            self.model_paths = {}
            if self.modality in model_bank[self.v_level]:
                self.model_paths[self.modality] = model_bank[self.v_level][self.modality]
            else:
                raise abort(400, {'message': f'No {self.modality} model for {self.v_level}.'}) 
        else: 
           raise abort(400, {'message': f'Model for {self.v_level} not implemented yet.'})

    def _get_window_level(self):
        #~ Query settings for specific models (window/level)
        settings_bank = {
            'C3': {
                'CT': {'window': 400, 'level': 50}, 
                'CBCT': {'window': 400, 'level': 50}
                },
            'T4': {
                'CT': {'window': 400, 'level': 50}
                },
            'T9': {
                'CT': {'window': 400, 'level': 50}
                },
            'T12': {
                'CT': {'window': 400, 'level': 50},
                'LowDoseCT': {'window': 400, 'level':50}
                },
            'L3': {
                'CT': {'window': 400, 'level': 50}
                },
            'L5': {
                'CT': {'window': 400, 'level': 50}
                },
            'Sacrum': {
                'MR': {'window': 2693, 'level': 307} # Range and mean of training set
                },
            'Thigh': {
                'CT': {'window': 400, 'level': 50}
                }
        }

        if self.v_level in settings_bank:
            if self.modality in settings_bank[self.v_level]:
                return settings_bank[self.v_level][self.modality]
            else:
                # Bad request since wrong modality
                raise abort(400, {'message': f'No {self.modality} model for {self.v_level}.'}) 
        else:
            # Bad request since wrong level
            raise abort(400, {'message': f'Model for {self.v_level} not implemented yet.'})

    def _set_options(self):
        #* Inference options
        self.sess_options = ort.SessionOptions()
        self.sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
        self.sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL  # ! or ORT_PARALLEL
        self.sess_options.log_severity_level = 4
        self.sess_options.enable_profiling = False
        self.sess_options.inter_op_num_threads = os.cpu_count() - 1
        self.sess_options.intra_op_num_threads = os.cpu_count() - 1

