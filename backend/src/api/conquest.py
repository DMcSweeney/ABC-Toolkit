"""
Conquest endpoints

"""
import os
import shutil
import ast
import logging
from flask import Blueprint, request, make_response, jsonify
import requests
import pydicom
import time


bp = Blueprint('/api/conquest', __name__)
logger = logging.getLogger(__name__)

spine_url = f"https://backend:5001/api/jobs/infer/spine"
segment_url = f"https://backend:5001/api/jobs/infer/segment"


@bp.route('/api/conquest/handle_trigger', methods=["POST"])
def handle_trigger():
    series_uid = request.args.get("series_uid")
    study_uid = request.args.get("study_uid")
    patient_id = request.args.get("patient_id")
    modality = request.args.get("modality")
    manufacturer= request.args.get("manufacturer")

    logger.info(f"Trigger received for patient_id: {patient_id} -- series: {series_uid} \
-- study: {study_uid} -- modality: {modality} -- manufacturer: {manufacturer}")
    
    ##TODO CGET the series? 
    patient_path = os.path.join('/data/inbox/', patient_id)

    if modality == 'CT' and manufacturer.lower() == 'elekta':
        modality='CBCT'

    ## Make the directories and organise the images on receipt
    image_path = os.path.join(patient_path, study_uid, series_uid, modality)
    logger.info(f'Moving image to: {image_path}')
    os.makedirs(image_path, exist_ok=True)
    
    ## Tags to read from every dicom header
    header_keys = {
        'patient_id': (0x0010, 0x0020), 
        'series_uid': (0x0020, 0x000e),
        'study_uid': (0x0020,0x000d),
        'modality': (0x0008,0x0060)
    }
    # ++++++++++++++++++++++++++
    def incoming_file_checks(filepath):
        if not os.path.isfile(filepath): return False ## Skip if directory

        ## Check that the DCM matches the study, series and modality of the request.
        dcm = pydicom.dcmread(filepath, stop_before_pixels=True)

        data = {}
        for key, tag in header_keys.items():
            group, element = tag
            data[key] = str(dcm[group, element].value) if [group, element] in dcm else None

        if not all([val == request.args.get(key) for key, val in data.items()]): ## If not all the elements match the request, skip
            # logger.info("Tags in header differ from those in request.")
            # logger.info(f"Header: {[(v, k) for v, k in data.items()]}")
            # logger.info(f"Request: {[(v, k) for v, k in request.args.items()]}")
            
            return False
        
        return True
    ##++++++++++++++++++++++++++++++++++
        
    for file in os.listdir(patient_path):
        filepath = os.path.join(patient_path, file)
        if not incoming_file_checks(filepath): continue ## If fails the checks (i.e. file header needs to match request header)

        if os.path.isfile(os.path.join(image_path, file)): continue ## Skip if already exists in destination
        shutil.move(filepath, image_path)
    logger.info("Moved")


    ## Then enqueue job
    if modality == 'CT':

        spine_body = {"input_path": image_path, "project": 'inbox', "patient_id": patient_id, 'series_uuid': series_uid, "modality": modality}
        spine = requests.post(spine_url, json=spine_body, verify=False)
        segment_body = {"input_path": image_path, "project": 'inbox', "patient_id": patient_id, 'series_uuid': series_uid, 
        "modality": modality,  "num_slices": "1"}
        segment_body['depends_on'] = spine.json()['job-ID'] ## Update segment job with the job id 
        segment = requests.post(segment_url, json=segment_body, verify=False) ## Submit segment job

    elif modality == 'CBCT':
        ## Assume this is a CBCT since Elekta don't manufacture CT scanners
        from app import mongo
        modality = 'CBCT'
        ## Query database for this patient and see if they have a planning CT labelled 
        response = mongo.db.spine.find_one({"patient_id": patient_id, "all_parameters.modality": "CT"})
        if response is None:
            raise ValueError(f"Could not find a labelled CT for patient: {patient_id}")

        from abcTK.segment.model_bank import model_bank
        levels = [k for k, v in model_bank.items() if modality in v.keys()]
        for level, position in response['prediction'].items():
            if level not in levels: 
                logger.info(f"No {modality} model for {level} vertebra, not submitting job...")
                continue
            segment_body = {"input_path": image_path, "project": 'inbox', "patient_id": patient_id, "slice_number":position[-1], "vertebra": level,
            'series_uuid': series_uid, "modality": modality,  "num_slices": "1", "resample": "True", "reference_scan": response['_id'],
              'calibrate_cbct': 'True', 'calibration_structure': 'brainstem'}
            logger.info(f"Submitting: {segment_body}")
            segment = requests.post(segment_url, json=segment_body, verify=False) ## Submit segment job

    elif modality == 'RTSTRUCT':
        ## Handle RT STRUCT
        # Insert into database, to make fetchable in future
        from app import mongo
        filepath = [os.path.join(image_path, x) for x in os.listdir(image_path)]
        assert len(filepath) == 1, f"One RTSTRUCT expected. Found {len(filepath)}"
        # Find the planning CT
        logger.info(f"Inserting RTSTRUCT into db. Path: {filepath[0]}" )
        res = mongo.db.images.find_one({'study_uuid': study_uid, 'modality': 'CT'})

        if res is None:
            ## Fetch the reference CT uid from the header
            dcm = pydicom.dcmread(filepath[0], stop_before_pixels=True)
            try:
                ref_series_uid = str(dcm[0x3006, 0x0010].value[0][0x3006, 0x0012].value[0][0x3006, 0x0014].value[0][0x0020, 0x000e].value)
                mongo.db.images.update_one({'_id': ref_series_uid}, {'$set': {'rtstruct_path': filepath[0]}}, upsert=True)
            except:
                raise ValueError(f'Could not find planning CT matching RTSTRUCT with studyUID: {study_uid}.')
        else:
            mongo.db.images.update_one({'_id': res['_id']}, {'$set': {'rtstruct_path': filepath[0]}}, upsert=True)

    elif modality in ["RTPLAN", "RTDOSE"]:
        logger.warning(f"{modality} received but will be ignored.")
        raise ValueError(f"{modality} received but will be ignored.")
    else:
        raise ValueError(f"Conquest pipeline can't handle modality provided ({modality}), must be one of CT, CBCT or RTSTRUCT")

    ## Output: report? success message? Link to sanity?
    res = make_response(jsonify({
        "message": "Job successfully submitted",
        "patient_id": patient_id,
        "series_uuid": series_uid,
    }), 200)

    return res
    