"""
Set of endpoints for segmentation side
"""

import os
import ast
import numpy as np
import logging
import SimpleITK as sitk
from datetime import datetime
import dill
from flask import Blueprint
from rq import Queue
from rq.job import Job


from abcTK.segment.engine import segmentationEngine
from abcTK.writer import sanityWriter
import abcTK.database.collections as cl

import dataclasses


bp = Blueprint('api/segment', __name__)
logger = logging.getLogger(__name__)

#########################################################
#* ==================== API =============================
#########################################################

#@bp.route('/api/infer/segment', methods=["GET", "POST"])
def infer_segment(req):
    """
    Endpoint for handling segmentation requests. Only handles one image, one level and one modality at a time.
    Make multiple requests if needed. 
    """

    # Import here to prevent issues when deserializing
    logger.info(f"Request received: {req}")

    ## Check required params
    check_params(req, required_params=["input_path", "project", "vertebra"])

    
    req['loader_function'], loader_name = get_loader_function(req['input_path'])
    if type(req["vertebra"]) == list:
        logger.error("Make multiple requests to use multiple models.")
        raise ValueError("Vertebra should be a string representing a single level. Make multiple requests to use different models.")

    req = handle_request(req)
    output_dir = os.path.join(req['APP_OUTPUT_DIR'], req["project"], req["patient_id"], req["series_uuid"])
    os.makedirs(output_dir, exist_ok=True)
    req['output_dir'] = output_dir
    
    Image = req['loader_function'](req['input_path'])
    req['origin'] = Image.GetOrigin()
    req['direction'] = Image.GetDirection()
    req['size'] = Image.GetSize()
    req['spacing'] = Image.GetSpacing()

    ## ++++++++++++++++   INFERENCE  +++++++++++++++++++++
    logger.info(f"Processing request: {req}")
    engine = segmentationEngine(**req)
    data, paths_to_sanity = engine.forward(**req)
    ###### UPDATE DATABASE ########
    update_database(req, data, paths_to_sanity)
    
    return 


########################################################
#* =============== HELPER FUNCTIONS =====================

def update_database(req, data, paths_to_sanity):
    from app import mongo

    database = mongo.db
    query = database.quality_control.find_one({'_id': req['series_uuid'], 'project': req['project']},
                                                {"_id": 1, "quality_control": 1, "paths_to_sanity_images": 1, 'qc_report': 1})
    labelling = database.images.find_one({'_id': req['series_uuid'], 'project': req['project']},
                                                {"_id": 1, "labelling_done":1})
    if labelling is not None:
        req['labelling_done'] = labelling['labelling_done']
    else:
        req['labelling_done'] = False

    qc = {req['vertebra']: {compartment: 2 for compartment in paths_to_sanity.keys() if compartment != 'ALL'}}
    qc_report = {req['vertebra']: {}}
   
    if query is not None: 
        logger.info(f"++++ Found existing entry in db: {query} +++++")
        #If an entry exists
        ## Update with existing values
        for k, v in query['paths_to_sanity_images'].items():
            if k in paths_to_sanity: # if this comprtment has been segmented, append or update                ...
                if type(v) == dict:
                    # Append. This should happen when adding a new vertebral level
                    tmp = {x: y for x, y in paths_to_sanity[k].items()}
                    tmp.update({x: y for x, y in v.items()})
                    paths_to_sanity.update({k: tmp})
            else:
                paths_to_sanity[k] = v
        
        for k, v in query['quality_control'].items():
            if k in qc: continue # Skip if level has just been segmented (i.e. set to 2)
            qc[k] = v

        if 'qc_report' in query:
            qc_report |= query['qc_report']


    ## To keep track of the values in QC dict, aggregate here and add a field to the db
    ## Used for fetching examples that need QA'ing/havefailed/passed all tests
    overall_qc_state = {}
    for vertebra in qc.keys():
        if any([val == 2 for val in qc[vertebra].values()]): ## We want to catch any that need doing first
            overall_qc_state[vertebra] = 2
        elif any([val == 0 for val in qc[vertebra].values()]): ## Then failures
            overall_qc_state[vertebra] = 0
        else:
            overall_qc_state[vertebra] = 1 ## Then successes
    
    ## Check if segmentation already done on this scan, if so update stats
    seg_query = database.segmentation.find_one({'_id': req['series_uuid'], 'project': req['project']}, {"_id": 1, "all_parameters": 1, "statistics": 1})
    all_parameters = {req['vertebra']: {k: str(v) for k, v in req.items()}}
    statistics = {req['vertebra']: data}
    if seg_query:
        # Keep other levels but delete the one that has been segmented
        if req['vertebra'] in seg_query['statistics']:
            del seg_query['statistics'][req['vertebra']]
        if req['vertebra'] in seg_query['all_parameters']:
            del seg_query['all_parameters'][req['vertebra']]

        all_parameters.update(seg_query['all_parameters'])
        statistics.update(seg_query['statistics'])

    fields = [ x.name for x in dataclasses.fields(cl.Images) ]
    image_update = cl.Images(_id=req['series_uuid'],  segmentation_done=True, **{k: str(v) for k, v in req.items() if k in fields})
    ## Insert into database
    segmentation_update = cl.Segmentation(_id=req['series_uuid'], project=req['project'], input_path=req['input_path'], 
                                            patient_id=req['patient_id'], series_uuid=req['series_uuid'], output_dir=req['output_dir'], statistics=statistics,
                                            all_parameters=all_parameters)
                                                            
    qc_update = cl.QualityControl(_id=req['series_uuid'], project=req['project'], input_path=req['input_path'], patient_id=req['patient_id'],
                                    series_uuid=req['series_uuid'], paths_to_sanity_images=paths_to_sanity, quality_control=qc, qc_report=qc_report,
                                    overall_qc_state = overall_qc_state
                                    )

    database.images.update_one({"_id": req['series_uuid']}, {"$set": image_update.__dict__}, upsert=True)
    logger.info(f"Set segmentation_done to True in collection: images")
    database.segmentation.update_one({"_id": req['series_uuid']}, {'$set': segmentation_update.__dict__}, upsert=True)
    logger.info(f"Inserted {segmentation_update.__dict__} into collection: spine")
    database.quality_control.update_one({"_id": req['series_uuid']}, {"$set": qc_update.__dict__}, upsert=True)
    logger.info(f"Inserted {qc_update.__dict__} into collection: quality_control")
    

def handle_request(req):
    header_keys = {
        'patient_id': '0010|0020',
        'study_uuid': '0020|000d',
        'series_uuid': '0020|000e',
        'pixel_spacing': '0028|0030',
        'slice_thickness': '0018|0050',
        'acquisition_date': '0008|0022',
        'series_date': '0008|0021',
        'study_date': '0008|0020',
    }
    from app import mongo 
    if os.path.isdir(req['input_path']):
        #dcm_files = [x for x in os.listdir(req['input_path']) if x.endswith(('dcm', 'DICOM', 'DCM'))]
        # if len(dcm_files) == 0:
        #     raise ValueError(f"No dicom files found in input path: {req['input_path']}")
        files = os.listdir(req['input_path'])
        items = read_dicom_header(os.path.join(req["input_path"], files[0]), header_keys=header_keys)

    elif os.path.isfile(req['input_path']):
        #TODO add reading nifti header
        items = read_nifti_header(req['input_path'], header_keys=header_keys)

    ## Add to request
    for key, val in items.items():
        if key in req:
            logger.info(f"{key} provided in request, ignoring DICOM header.")
            continue
        if key == 'patient_id' and val == '':
            raise ValueError("Patient ID not found in DICOM header. Please provide with request.")
        if key == 'series_uuid' and val == None:
            raise ValueError("Series UUID not found in DICOM header. Please provide with request.")
        
        if key == 'acquisition_date':
            if val is None:
                # Check the series_date is not empty and overwrite
                if items['series_date'] is not None and items['study_date'] is None:
                    logger.info(f"AcquisitionDate and StudyDate not found in header. Overwriting with SeriesDate: {items['series_date']}")
                    val = datetime.strptime(items['series_date'], '%Y%m%d').date().strftime('%d-%m-%Y')
                elif items['study_date'] is not None and items['series_date'] is None:
                    logger.info(f"AcquisitionDate and SeriesDate not found in header. Overwriting with StudyDate: {items['study_date']}")
                    val = datetime.strptime(items['study_date'], '%Y%m%d').date().strftime('%d-%m-%Y')
                else:
                    logger.warning("AcquisitionDate, SeriesDate and StudyDate not found in header. Provide acquisition_date in request if needed.")
            else:
                val = datetime.strptime(val, '%Y%m%d').date().strftime('%d-%m-%Y')
                
        if key in ['series_date', 'study_date'] and val is not None:
            val = datetime.strptime(val, '%Y%m%d').date().strftime('%d-%m-%Y')

        if key == 'pixel_spacing' and "\\" in val:
            val = val.split('\\')
            val = [float(x) for x in val]
            req['X_spacing'] = val[0]
            req['Y_spacing'] = val[1]
            continue
        
        req[key] = val

    # WORLDMATCH OFFSET 
    # TODO HANDLE MR OFFSET - not sure of details
    if 'worldmatch_correction' not in req:
        logger.info("Worldmatch correction (-1024 HU) will not be applied. Overwrite with 'worldmatch_correction' in request.")
        req['worldmatch_correction'] = False
    else:
        if isinstance(req['worldmatch_correction'], str):
            if req['worldmatch_correction'].lower() in ['false', '0', 'no']:
                req['worldmatch_correction'] = False
            elif req['worldmatch_correction'].lower() in ['true', '1', 'yes']:
                req['worldmatch_correction'] = True
        else:
            raise ValueError("Worldmatch correction should be a string (True/False)")

    # BONE MASKS
    if 'generate_bone_mask' not in req:
        logger.info("Bone mask will be regenerated. This might slow things down. Overwrite with 'generate_bone_mask' in request (True-> regenerate; False-> skip).")
        req['generate_bone_mask'] = True
    elif type(req['generate_bone_mask']) == str:
        if req['generate_bone_mask'].lower() in ['false', '0', 'no']:
            req['generate_bone_mask'] = False
            logger.info(f"Converted generate_bone_mask to bool: {req['generate_bone_mask']}")
        elif req['generate_bone_mask'].lower() in ['true', '1', 'yes']:
            req['generate_bone_mask'] = True
            logger.info(f"Converted generate_bone_mask to bool: {req['generate_bone_mask']}")
        else:
            # If can't be converted to bool assume path
            logger.info(f"Will not regenerate bone mask. Path to provided: {req['generate_bone_mask']}")

    
    if 'override_spine_sanity' in req:
        if isinstance(req['override_spine_sanity'], str):
            if req['override_spine_sanity'].lower() in ['false', '0', 'no']:
                req['override_spine_sanity'] = False
            elif req['override_spine_sanity'].lower() in ['true', '1', 'yes']:
                req['override_spine_sanity'] = True
            else:
                raise ValueError(f"Can't convert override_spine_sanity arg ({req['override_spine_sanity']}) to bool")
        
    # SLICE NUMBER
    if "slice_number" not in req:
        ## Check the spine collection for vertebra
        if 'reference_scan' in req:
            match = mongo.db.spine.find_one({"_id": req['reference_scan']})
        else:
            match = mongo.db.spine.find_one({"_id": req['series_uuid']})

        if match is None or req["vertebra"] not in match["prediction"]:
            raise ValueError("Could not find a slice number for the requested vertebra.")

        req['slice_number'] = match["prediction"][req["vertebra"]][-1]
        logger.info(f"Found slice number {req['slice_number']} for {req['vertebra']}")
    else:
        ## If user provides a slice number, override the previous spine sanity image and generate a new image with only the level provided.  
        req['override_spine_sanity'] = True 

    if type(req['slice_number']) == str:
        req['slice_number'] = int(req['slice_number'])
    
    # MODALITY
    if "modality" not in req:
        ## If user doesn't provide modality, add default (CT)
        #TODO should this come from header? Might not handle CBCTs?
        logger.info("Assuming default modality: CT")
        req["modality"] = "CT"
    
    # NUM SLICES AROUND REFERENCE
    if "num_slices" not in req:
        ## If user doesn't provide modality, add default (CT)
        logger.info("Only segmenting reference slice.")
        req["num_slices"] = 0
    elif type(req["num_slices"]) == str:
        req['num_slices'] = int(req['num_slices'])

    ## Muscle and fat thresholds
    if 'muscle_threshold' in req:
        req['muscle_threshold'] = ast.literal_eval(req['muscle_threshold'])
        req['muscle_threshold'] = [None if x == 'None' else x for x in req['muscle_threshold']]
        logger.info(f"Reading muscle_threshold from request: Low/High {req['muscle_threshold']}")

    if 'fat_threshold' in req:
        req['fat_threshold'] = ast.literal_eval(req['fat_threshold'])
        req['fat_threshold'] = [None if x == 'None' else x for x in req['fat_threshold']]
        logger.info(f"Reading fat_threshold from request: Low/High {req['fat_threshold']}")

    if 'resample' in req:
        # Convert to a boolean
        if isinstance(req['resample'], str):
            if req['resample'].lower() in ['false', '0', 'no']:
                req['resample'] = False
            elif req['resample'].lower() in ['true', '1', 'yes']:
                req['resample'] = True
            else:
                raise ValueError(f"Can't convert resample arg ({req['resample']}) to bool")
        else:
            req['resample'] = ast.literal_eval(req['resample'])
            assert isinstance(req['resample'], bool), f"Argument 'resample' is not a bool! Received: {req['resample']}"

        # Check that other args also given
        valid_args = ['resample_spacing', 'resample_transform', 'reference_scan']
        assert any([x in req for x in valid_args]), f"Resampling requested but missing required parameters. Provide one of: {valid_args}"

        for arg in valid_args:
            if arg in req:
                if arg == 'resample_transform':
                    assert 'reference_scan' in req, f"reference_scan needed in request to apply transform to moving image"
                if not isinstance(req[arg], str):
                    logger.info(f"{arg} with value {req[arg]} is not a string. Trying to evaluate type.")
                    req[arg] = ast.literal_eval(req[arg])

    if 'scale_intensity' in req:
        if isinstance(req['scale_intensity'], str):
            req['scale_intensity'] = float(req['scale_intensity'])
    

    if 'calibrate_cbct' in req:
        # Convert to a boolean
        if isinstance(req['calibrate_cbct'], str):
            if req['calibrate_cbct'].lower() in ['false', '0', 'no']:
                req['calibrate_cbct'] = False
            elif req['calibrate_cbct'].lower() in ['true', '1', 'yes']:
                req['calibrate_cbct'] = True
            else:
                raise ValueError(f"Can't convert resample arg ({req['calibrate_cbct']}) to bool")
        else:
            req['calibrate_cbct'] = ast.literal_eval(req['calibrate_cbct'])
            assert isinstance(req['calibrate_cbct'], bool), f"Argument 'calibrate_cbct' is not a bool! Received: {req['calibrate_cbct']}"

        if req['calibrate_cbct'] and 'scale_intensity' in req:
            logger.warning('Ignoring scale_intensity argument as calibrate_cbct set to True. Will try to auto calibrate CBCT.')
            del req['scale_intensity']

        if req['calibrate_cbct']:
            assert 'reference_scan' in req, f"CBCT calibration requested but reference scan has not been specified. Specify the planning CT to use as reference."
            assert 'calibration_structure' in req, f"CBCT calibration requested but calibration_structure has not been specified. Specify the structure in RTSTRUCT to use for calibration."

            # Format calibration structure
            if not isinstance(req['calibration_structure'], str):
                logger.error(f"calibration_structure is not a string ({req['calibration_structure']}). Support for other datatypes not implemented! Please pass a string")
                raise ValueError
                

    if 'shift_intensity' in req:
        if isinstance(req['shift_intensity'], str):
            req['shift_intensity'] = float(req['shift_intensity'])

    return req


def get_loader_function(path):
    def load_numpy(path):
        img = np.load(path)
        return sitk.GetImageFromArray(img)

    def load_nifty(path):
        #* Read nii volume
        return sitk.ReadImage(path)
    
    def load_nrrd(path):
        return sitk.ReadImage(path)

    def load_dcm(path):
        #* Read DICOM directory
        reader = sitk.ImageSeriesReader()
        dcm_names = reader.GetGDCMSeriesFileNames(path)
        reader.SetFileNames(dcm_names)
        return reader.Execute()

    if os.path.isdir(path):
        ## Check at least one dicom file
        logger.info("Input is a directory, assuming DICOM.")
        #dcm = [x for x in os.listdir(path) if x.endswith(('dcm', 'DICOM', 'DCM'))]
        return load_dcm, 'dicom' ## Loader function
        # if len(dcm) != 0:
        #     return load_dcm, 'dicom' ## Loader function
        # else:
        #     raise ValueError('Input is not a directory of dicom files. Please use full path if using other format.')

    elif os.path.isfile(path):
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
    else:
        logger.warning("Input is not a directory or a file... Not sure how you did that")


def read_nifti_header(path, header_keys):
    Image = sitk.ReadImage(path)
    data = {}
    for k in header_keys.keys():
        if k == 'pixel_spacing':
            spacing = Image.GetSpacing()[:-1]
            data['X_spacing'] = str(spacing[0])
            data['Y_spacing'] = str(spacing[1])
        if k == 'slice_thickness':
            thickness = Image.GetSpacing()[-1]
            data[k] = thickness
        if k in ['acquisition_date', 'study_uuid', 'series_date', 'study_date']:
            #TODO get this from header
            data[k] = None
    return data
        
def read_dicom_header(path, header_keys):
    reader = sitk.ImageFileReader()
    reader.LoadPrivateTagsOn()
    reader.SetFileName(path)
    reader.ReadImageInformation()
    metadata = {}
    for k in reader.GetMetaDataKeys():
        v = reader.GetMetaData(k)
        if v == '': #Replace empty string
            v=None
        metadata[k] = v
    data = {}
    for key, val in header_keys.items():
        try:
            data[key] = metadata[val]
        except KeyError:
            data[key] = None # For sql
    return data

def check_params(req, required_params = ["input", "project", "patient_id", "scan_id"]):
    ## Check all args have been provided to inference call
    test = [x in req for x in required_params]
    if not all(test):
        logger.info(f"Some required parameters are missing. Did you provide the following? {required_params}")
        raise ValueError(f"Some required parameters are missing. Did you provide the following? {required_params}") ## Bad request
