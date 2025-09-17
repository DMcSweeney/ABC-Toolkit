"""
Set of endpoints for spine labelling
"""
import os
import numpy as np
import torch
from datetime import datetime
from flask import Blueprint
import SimpleITK as sitk
import json
import logging
import dataclasses
from tqdm import tqdm

from abcTK.spine.server import spineApp
from abcTK.writer import sanityWriter
import abcTK.database.collections as cl


#import models


bp = Blueprint('api/spine', __name__)
logger = logging.getLogger(__name__)

#########################################################
#* ==================== API =============================
#########################################################

#@bp.route('/api/infer/spine', methods=["GET", "POST"])
def infer_spine(req):
    from app import mongo
    logger.info(f"Request received: {req}")

    if not torch.cuda.is_available():
        logger.error("No GPU detected")
        raise ValueError("No GPU detected") ## Internal server error 

    check_params(req, required_params=["input_path", "project"])
    req['loader_function'] = get_loader_function(req['input_path'])

    req = handle_request(req)

    if req['modality'] != 'CT':
        raise ValueError(f"Spine labelling limited to CT ... Image is: {req['modality']}") ## Internal server error 

    # Load the image into SimpleITK and extract image info --> Needed for resampling onto this image
    Image = req['loader_function'][0](req['input_path'])
    req['origin'] = Image.GetOrigin()
    req['direction'] = Image.GetDirection()
    req['size'] = Image.GetSize()
    req['spacing'] = Image.GetSpacing()

    logger.info(f"Processing: {req}")
    ## Start the spineApp
    app = init_app()
    
    output_dir = os.path.join(req['APP_OUTPUT_DIR'], req["project"], req['patient_id'], req["series_uuid"])
    
    os.makedirs(output_dir, exist_ok=True)

    # +++++ INFERENCE +++++

    response = app.infer(request = {
        "model": "vertebra_pipeline", 
        "image": req['input_path'],
        "worldmatch_correction": req['worldmatch_correction']
        })#

    logger.info(f"Spine labelling complete: {response}")
    
    res, output_filename = handle_response(req['input_path'], response, output_dir, req['loader_function'][0])
    
    #######  UPDATE DATABASE #######
    # Updates
    if res['status_code'] == 200:
        update_database(req, res, output_dir)


    return res


########################################################
#* =============== HELPER FUNCTIONS =====================
########################################################
def update_database(request, response, output_dir):
    from app import mongo
    
    # Create updates
    fields = [ x.name for x in dataclasses.fields(cl.Images) ]

    res = mongo.db.images.find_one({'_id': request['series_uuid']})
    if res is not None and 'rtstruct_path' in res:
        request['rtstruct_path'] = res['rtstruct_path']
    else:
        request['rtstruct_path'] = ''
        
    image_update = cl.Images(_id=request['series_uuid'],  segmentation_done=True, **{k: str(v) for k, v in request.items() if k in fields} )

    spine_update = cl.Spine(_id=request['series_uuid'], output_dir=output_dir, prediction=response['prediction'],
                            project = request['project'], input_path=request['input_path'], patient_id=request['patient_id'],
                            series_uuid=request['series_uuid'], all_parameters={k: str(v) for k, v in request.items() if k not in ['loader_function', 'APP_OUTPUT_DIR']}, 
                            )
    qc_update = cl.QualityControl(_id=request['series_uuid'], project = request['project'], input_path=request['input_path'],
                                patient_id=request['patient_id'], series_uuid=request['series_uuid'],
                                paths_to_sanity_images={'SPINE': response['quality_control_image']},
                                quality_control={}, qc_report={}, overall_qc_state={}
                                )
    
    database = mongo.db # Access the database
    
    database.images.update_one({"_id": image_update._id}, {'$set': image_update.__dict__}, upsert=True)
    logger.info(f"Inserted {image_update.__dict__} into collection: images")

    database.spine.update_one({"_id": spine_update._id}, {'$set': spine_update.__dict__}, upsert=True)
    logger.info(f"Inserted {spine_update.__dict__} into collection: spine")
    

    database.quality_control.update_one({"_id": qc_update._id}, {'$set': qc_update.__dict__}, upsert=True)
    logger.info(f"Inserted {qc_update.__dict__} into collection: quality_control")



def handle_request(req):
    ## Handle paramaters and extract info from dicom header if not provided.

    header_keys = {
        'patient_id': '0010|0020',
        'study_uuid': '0020|000d',
        'series_uuid': '0020|000e',
        'pixel_spacing': '0028|0030',
        'slice_thickness': '0018|0050',
        'acquisition_date': '0008|0022',
        'series_date': '0008|0021',
        'study_date': '0008|0020'
    }
    # If directory, assume dicom
    if os.path.isdir(req['input_path']):
        #dcm_files = [x for x in os.listdir(req['input_path']) if x.endswith(('dcm', 'DICOM', 'DCM'))]
        # if len(dcm_files) == 0:
        #     raise ValueError(f"No dicom files found in input path: {req['input_path']}")
        files = os.listdir(req['input_path'])
        if 'series_uuid' in req:
            reader = sitk.ImageSeriesReader()
            filenames = reader.GetGDCMSeriesFileNames(req['input_path'], req['series_uuid'])
            if filenames:
                ## If series_uuid provided only read that series
                logger.info(f"Series UUID provided: {req['series_uuid']}, only reading this series.")
                items = read_dicom_header_from_series_uuid(req['input_path'], req['series_uuid'], header_keys=header_keys)
            else:
                logger.warning(f"No series found with series_uuid: {req['series_uuid']}.\n Assuming this is a custom uuid and that all files in {req['input_path']} belong to one series.")
                items = read_dicom_header(os.path.join(req["input_path"], files[0]), header_keys=header_keys)
        else:
            items = read_dicom_header(os.path.join(req["input_path"], files[0]), header_keys=header_keys)


    elif os.path.isfile(req['input_path']):
        #TODO add reading nifti header
        items = read_nifti_header(req['input_path'], header_keys=header_keys)
    else:
        raise ValueError("input_path is not a directory or a file.")

    ## Add to request
    for key, val in items.items():
        if key in req:
            logger.info(f"{key} provided in request, ignoring DICOM header.")
            continue
        if key == 'patient_id' and val == '':
            raise ValueError("Patient ID not found in header. Please provide with request.")
        if key == 'series_uuid' and val == None:
            raise ValueError("Series UUID not found in header. Please provide with request.")
        
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
            
    # MODALITY
    if "modality" not in req:
        ## If user doesn't provide modality, add default (CT)
        #TODO should this come from header? Might not handle CBCTs?
        logger.info("Assuming default modality: CT")
        req["modality"] = "CT"
    
    return req

def get_loader_function(path):
    def load_numpy(path):
        img = np.load(path)
        return sitk.GetImageFromArray(img)

    def load_nifty(path):
        #* Read nii volume
        return sitk.ReadImage(path)
    
    def load_dcm(path):
        #* Read DICOM directory

        reader = sitk.ImageSeriesReader()
        dcm_names = [reader.GetGDCMSeriesFileNames(path, series_id) for series_id in reader.GetGDCMSeriesIDs(path)]
        assert len(dcm_names) > 0, f"No DICOM series found in {path}"
        ## If more than 1
        logger.info(f"Detected {len(dcm_names)} series in directory.")
        if len(dcm_names) > 1:
            ## Select the one with most files and read that
            logger.warning("Multiple series detected, selecting the one with most files.")
            dcm_names.sort(key=len, reverse=True)

        reader.SetFileNames(dcm_names[0])
        return reader.Execute()

    if os.path.isdir(path):
        ## Check at least one dicom file
        logger.info("Input is a directory, assuming DICOM.")
        #dcm = [x for x in os.listdir(path) if x.endswith(('dcm', 'DICOM', 'DCM'))]
        return load_dcm, 'dicom'
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
            else:
                logger.warning(f"Unrecognized file extension: {path}")
        
        if ext in ['.nii', '.nii.gz']:
            return load_nifty, 'nifty'
        elif ext in ['.npy', '.npz']:
            return load_numpy, 'numpy'

def read_dicom_header_from_series_uuid(path, series_uuid, header_keys):
    reader = sitk.ImageSeriesReader()
    filenames = reader.GetGDCMSeriesFileNames(path, series_uuid)
    reader = sitk.ImageFileReader()
    reader.SetFileName(filenames[0])
    reader.LoadPrivateTagsOn()
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


def init_app():
    # Initialise the spine app
    
    app_dir = os.path.dirname(__file__)
    studies =  "https://127.0.0.1:8989" #Just points to an empty address - needed for monaiLabelApp
    config = {
        "models": "find_spine,find_vertebra,segment_vertebra",
        "preload": "false",
        "use_pretrained_model": "true"
    }   
    return spineApp(app_dir, studies, config)

def json_to_file(json_payload, output_path, filename='spine-output.json'):
    """
    Convert the json output with levels into a mask.
    Not ideal for storage but better integration with XNAT and reduces transform-related errors
    """
    output_filename = os.path.join(output_path, filename)
    with open(output_filename, 'w') as f:
        json.dump(json_payload, f)

def handle_response(image_path, res, output_dir, loader_function):
    """
    Handle the reply from inference 
    """
    json_output_path = os.path.join(output_dir, 'json')
    os.makedirs(json_output_path, exist_ok=True)
    writer = sanityWriter(output_dir, vertebra=None, slice_number=None, num_slices=None, window=1000, level=500, modality='CT')

    label = res["file"]
    label_json = res["params"]

    if label is None and label_json is None:
        #* This is the case if no centroids were detected
        logger.error("No centroids detected")
        res['status_code'] = 500
        output_filename = None
    
    elif label is None and label_json is not None:
        ## Prettify the json
        json_to_file(label_json, json_output_path, filename='all-spine-outputs.json')
        pretty_json = prettify_json(label_json)
        json_to_file(pretty_json, json_output_path)
        output_filename = writer.write_spine_sanity('SPINE', image_path, pretty_json, loader_function)

        res['status_code'] = 200
        res['prediction'] = pretty_json
        res['quality_control_image'] = output_filename

    else:
        # This should never happen... Would like to add this though
        logger.error("Somehow you got here.\
                      This means the spine module tried to write vertebral masks, which hasn't been implemented.\
                      I have no idea how you managed that... Well done!!")

        res['status_code'] = 500
        output_filename = None

    return res, output_filename

def prettify_json(input_json):
    ## Clean spine app predictions
    labels, centroids = input_json['label_names'], input_json['centroids']
    vert_lookup = {val: key for key, val in labels.items()}
    dict_ = {}
    for centroid in centroids:
        for val in centroid.values():
            level = vert_lookup[val[0]]
            dict_[level] = [x for x in val[1:]]
    return dict_

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
        if k in ['acquisition_date', 'study_uuid', 'series_uuid']:
            #TODO get this from header
            data[k] = None
    return data

# def filter_DICOM_on_affine_matrix(filepaths):
#     rotations = {}
#     metadata = {}
#     for filepath in filepaths:
#         reader = sitk.ImageFileReader()
#         reader.SetFileName(filepath)
#         slice_ = reader.Execute()
#         #rot = str(slice_.GetDirection())
#         meta = read_dicom_header(filepath, header_keys={'image_type': '0008|0008'})['image_type']
#         # Add or append entry
#         if meta in metadata:
#             metadata[meta].append(filepath)
#         else:
#             metadata[meta] = [filepath]
        
#     # print(f'------- I FOUND {len(list(rotations.keys()))} rotations ---- ', flush=True)
#     # print(f'------- I FOUND {len(list(metas.keys()))} origins ---- ', flush=True)
#     # print(list(metas.keys()), flush=True)
#     # # Get key, val with longest list (most entries)
#     # common_rotation = set(max(rotations.values(), key = lambda x: len(set(x))))
#     return list(set(max(metadata.values(), key = lambda x: len(set(x)))))
#     #return list(set.intersection(common_rotation, common_meta))
