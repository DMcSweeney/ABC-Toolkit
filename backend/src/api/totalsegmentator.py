"""
TotalSegmentator v2 ()

https://github.com/wasserth/TotalSegmentator?tab=readme-ov-file
"""
import os
import logging
import subprocess
from flask import Blueprint, request, make_response, jsonify, current_app
import SimpleITK as sitk
from datetime import datetime
from totalsegmentator.python_api import totalsegmentator

bp = Blueprint('api/totalsegmentator', __name__)
logger = logging.getLogger(__name__)


@bp.route('/api/totalsegmentator', methods=["POST"])
def infer_totalsegmentator():
    """
    Totalsegmentator assumes DICOM is one folder by series? 
    """
    req = request.get_json()
    logger.info(f"Request received: {req}")
    req['APP_OUTPUT_DIR'] = current_app.config['OUTPUT_DIR']
    ## Check required params
    check_params(req, required_params=["input_path", "project"])
    
    ## Fetch info from metadata if not provided
    req = handle_request(req)
    output_dir = os.path.join(req['APP_OUTPUT_DIR'], req["project"], req["patient_id"], req["series_uuid"], "TotalSegmentator")
    os.makedirs(output_dir, exist_ok=True)
    req['output_dir'] = output_dir
    
    start = datetime.now()
    totalsegmentator(req['input_path'], req['output_dir'], ml=True, preview=True, verbose=True)
    #subprocess.run([f"TotalSegmentator -i {req['input_path']} -o {req['output_dir']} --verbose --device gpu"], shell=True, check=True) 
    # --ml --statistics --body_seg --preview
    res = make_response(jsonify({
        "message": 
        f"TotalSegmentator inference successful. Total time (s): {datetime.now()-start}"
        }),200)
    
    return res

def handle_request(req):
    from app import mongo 

    dcm_files = [x for x in os.listdir(req['input_path']) if x.endswith('.dcm')]
    if len(dcm_files) == 0:
        raise ValueError(f"No dicom files found in input path: {req['input_path']}")
    
    header_keys = {
        'patient_id': '0010|0020',
        'study_uuid': '0020|000D',
        'series_uuid': '0020|000e',
        'pixel_spacing': '0028|0030',
        'slice_thickness': '0018|0050',
        'acquisition_date': '0008|0022'
    }
    items = read_dicom_header(os.path.join(req["input_path"], dcm_files[0]), header_keys=header_keys)

    ## Add to request
    for key, val in items.items():
        if key in req:
            logger.info(f"{key} provided in request, ignoring DICOM header.")
            continue
        if key == 'patient_id' and val == '':
            raise ValueError("Patient ID not found in DICOM header. Please provide with request.")
        if key == 'series_uuid' and val == None:
            raise ValueError("Series UUID not found in DICOM header. Please provide with request.")
        
        if key == 'acquisition_date' and val is not None:
            val = datetime.strptime(val, '%Y%m%d').date().strftime('%d-%m-%Y')

        if key == 'pixel_spacing' and "\\" in val:
            val = val.split('\\')
            val = [float(x) for x in val]
            req['X_spacing'] = val[0]
            req['Y_spacing'] = val[1]
            continue
        
        req[key] = val

    return req

def check_params(req, required_params = ["input", "project", "patient_id", "scan_id"]):
    ## Check all args have been provided to inference call
    test = [x in req for x in required_params]
    if not all(test):
        logger.info(f"Some required parameters are missing. Did you provide the following? {required_params}")
        raise ValueError(f"Some required parameters are missing. Did you provide the following? {required_params}") ## Bad request

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
        if type(v) == str:
            v = v.strip()
        metadata[k] = v
    data = {}
    for key, val in header_keys.items():
        try:
            data[key] = metadata[val]
        except KeyError:
            data[key] = None # For sql
    return data