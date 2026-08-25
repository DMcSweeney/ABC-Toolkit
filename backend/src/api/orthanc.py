"""
Orthanc endpoints

"""
import os
import logging
import pydicom
from flask import Blueprint, request, make_response, jsonify
import requests

from abcTK.constants import UNASSIGNED_PROJECT

bp = Blueprint('/api/orthanc', __name__)
logger = logging.getLogger(__name__)

ORTHANC_URL = "https://orthanc:8042"
ORTHANC_AUTH = (os.environ['ORTHANC_USER'], os.environ['ORTHANC_PASSWORD'])

spine_url = f"https://backend:5001/api/jobs/infer/spine"
segment_url = f"https://backend:5001/api/jobs/infer/segment"
register_url = f"https://backend:5001/api/jobs/infer/register"


@bp.route('/api/orthanc/handle_trigger', methods=["POST"])
def handle_trigger():
    series_uid = request.args.get("series_uid")
    study_uid = request.args.get("study_uid")
    patient_id = request.args.get("patient_id")
    modality = request.args.get("modality")
    manufacturer_model_name = request.args.get("manufacturer_model_name") or ""
    orthanc_series_id = request.args.get("orthanc_series_id")

    logger.info(f"Trigger received for patient_id: {patient_id} -- series: {series_uid} \
-- study: {study_uid} -- modality: {modality} -- manufacturer_model_name: {manufacturer_model_name}")

    if modality == 'CT' and 'elekta' in manufacturer_model_name.lower():
        modality = 'CBCT'

    ## Make the directories and pull the images from Orthanc's REST API
    patient_path = os.path.join('/data/inbox/', patient_id)
    image_path = os.path.join(patient_path, study_uid, series_uid, modality)
    logger.info(f'Fetching series {orthanc_series_id} from Orthanc into: {image_path}')
    os.makedirs(image_path, exist_ok=True)

    instances = requests.get(f"{ORTHANC_URL}/series/{orthanc_series_id}/instances", auth=ORTHANC_AUTH, verify=False).json()
    for instance in instances:
        instance_id = instance['ID'] if isinstance(instance, dict) else instance
        main_tags = instance.get('MainDicomTags', {}) if isinstance(instance, dict) else {}
        filename = f"{main_tags.get('SOPInstanceUID', instance_id)}.dcm"

        dest = os.path.join(image_path, filename)
        if os.path.isfile(dest):
            continue ## Skip if already fetched (idempotent re-delivery)

        content = requests.get(f"{ORTHANC_URL}/instances/{instance_id}/file", auth=ORTHANC_AUTH, verify=False).content
        with open(dest, 'wb') as f:
            f.write(content)
    logger.info(f"Fetched {len(instances)} instance(s)")


    ## Then enqueue job
    if modality == 'CT':

        spine_body = {"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id, 'series_uuid': series_uid, "modality": modality}
        spine = requests.post(spine_url, json=spine_body, verify=False)
        segment_body = {"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id, 'series_uuid': series_uid,
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

        ## The CBCT and planning CT are acquired on different machines with no shared
        ## coordinate frame and no exportable registration object from MOSAIQ, so a
        ## registration job runs first to align them and correct the vertebra slice
        ## numbers before segmentation - see abcTK/inference/register.py.
        register_body = {"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id,
        'series_uuid': series_uid, "reference_scan": response['_id']}
        logger.info(f"Submitting: {register_body}")
        register = requests.post(register_url, json=register_body, verify=False) ## Submit registration job

        from abcTK.segment.model_bank import model_bank
        levels = [k for k, v in model_bank.items() if modality in v.keys()]
        for level in response['prediction'].keys():
            if level not in levels:
                logger.info(f"No {modality} model for {level} vertebra, not submitting job...")
                continue
            segment_body = {"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id, "vertebra": level,
            'series_uuid': series_uid, "modality": modality,  "num_slices": "1", "resample": "True", "reference_scan": response['_id'],
              'calibrate_cbct': 'True', 'calibration_structure': 'brainstem'}
            segment_body['depends_on'] = register.json()['job-ID'] ## Segment job waits for the registration to complete
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
        raise ValueError(f"Orthanc pipeline can't handle modality provided ({modality}), must be one of CT, CBCT or RTSTRUCT")

    ## Output: report? success message? Link to sanity?
    res = make_response(jsonify({
        "message": "Job successfully submitted",
        "patient_id": patient_id,
        "series_uuid": series_uid,
    }), 200)

    return res
