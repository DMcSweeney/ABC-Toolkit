"""
Orthanc endpoints

"""
import os
import uuid
import logging
import dill
import pydicom
from flask import Blueprint, request, make_response, jsonify, current_app
from rq import Queue, Callback
from rq.job import Dependency

from abcTK.constants import UNASSIGNED_PROJECT
from abcTK.orthanc_client import (INBOX_DIR, fetch_series, lookup_series, delete_series, retention_days,
                                  cleanup_series, on_pipeline_root_failure)

bp = Blueprint('/api/orthanc', __name__)
logger = logging.getLogger(__name__)

SUPPORTED_MODALITIES = ('CT', 'CBCT', 'RTSTRUCT')


@bp.route('/api/orthanc/handle_trigger', methods=["POST"])
def handle_trigger():
    series_uid = request.args.get("series_uid")
    study_uid = request.args.get("study_uid")
    patient_id = request.args.get("patient_id")
    modality = request.args.get("modality")
    manufacturer_model_name = request.args.get("manufacturer_model_name") or ""
    orthanc_series_id = request.args.get("orthanc_series_id")
    remote_aet = request.args.get("remote_aet") or ""
    days = retention_days(remote_aet)

    logger.info(f"Trigger received for patient_id: {patient_id} -- series: {series_uid} \
-- study: {study_uid} -- modality: {modality} -- manufacturer_model_name: {manufacturer_model_name} \
-- sender: {remote_aet or 'unknown'} (retention: {days} days)")

    if modality == 'CT' and 'elekta' in manufacturer_model_name.lower():
        ## Assume this is a CBCT since Elekta don't manufacture CT scanners
        modality = 'CBCT'

    if modality not in SUPPORTED_MODALITIES:
        ## Not fetched at all - nothing to process, so nothing to clean up in the inbox.
        logger.warning(f"{modality} received but will be ignored.")
        if days == 0:
            delete_series(orthanc_series_id)
        return make_response(jsonify({
            "message": f"{modality} ignored - the Orthanc pipeline only handles {', '.join(SUPPORTED_MODALITIES)}",
            "patient_id": patient_id,
            "series_uuid": series_uid,
        }), 200)

    ## Everything for this series' pipeline lives under series_dir, so cleanup is a single rmtree
    series_dir = os.path.join(INBOX_DIR, patient_id, study_uid, series_uid)
    image_path = os.path.join(series_dir, modality)
    cleanup_ctx = {"inbox_dir": series_dir, "orthanc_series_ids": [orthanc_series_id], "retention_days": days}

    try:
        logger.info(f'Fetching series {orthanc_series_id} from Orthanc into: {image_path}')
        num_instances = fetch_series(orthanc_series_id, image_path)
        logger.info(f"Fetched {num_instances} instance(s)")

        if modality == 'CT':
            _submit_ct(image_path, patient_id, series_uid, cleanup_ctx)
        elif modality == 'CBCT':
            _submit_cbct(image_path, series_dir, patient_id, series_uid, cleanup_ctx)
        elif modality == 'RTSTRUCT':
            _record_rtstruct(image_path, study_uid, series_uid)
            cleanup_series(cleanup_ctx) ## No jobs to wait for
    except Exception:
        ## Clean up regardless of the failure, then let the app's error handlers report it
        try:
            cleanup_series(cleanup_ctx)
        except Exception:
            logger.exception(f"Cleanup after failed trigger also failed for series {series_uid}")
        raise

    ## Output: report? success message? Link to sanity?
    res = make_response(jsonify({
        "message": "Job successfully submitted",
        "patient_id": patient_id,
        "series_uuid": series_uid,
    }), 200)

    return res


#* ===================== HELPERS =====================

def _submit_pipeline(root_func, root_queue, root_body, segment_bodies, cleanup_ctx):
    """
    Enqueue root job -> segment jobs (one per body) -> cleanup job.

    The cleanup job waits for every segment job whether it succeeds or fails. If the root job
    fails, its segment jobs never run (and so the cleanup job would never become ready), so the
    root job's on_failure callback cancels them and cleans up instead - job IDs are generated
    up front so the callback knows what to cancel.
    """
    from app import redis
    from abcTK.inference.segment import infer_segment

    segment_ids = [str(uuid.uuid4()) for _ in segment_bodies]
    cleanup_id = str(uuid.uuid4())
    cleanup_ctx = {**cleanup_ctx, "dependent_job_ids": segment_ids + [cleanup_id]}

    root = Queue(root_queue, connection=redis, serializer=dill).enqueue(
        root_func, root_body, job_timeout=300, meta={"cleanup_ctx": cleanup_ctx},
        on_failure=Callback(on_pipeline_root_failure, timeout=300))

    segment_queue = Queue('default', connection=redis, serializer=dill)
    for body, job_id in zip(segment_bodies, segment_ids):
        logger.info(f"Submitting: {body}")
        segment_queue.enqueue(infer_segment, body, depends_on=root.id, job_id=job_id)

    Queue('low', connection=redis, serializer=dill).enqueue(
        cleanup_series, cleanup_ctx, job_id=cleanup_id,
        depends_on=Dependency(jobs=segment_ids or [root.id], allow_failure=True))


def _submit_ct(image_path, patient_id, series_uid, cleanup_ctx):
    from abcTK.inference.spine import infer_spine
    from abcTK.segment.model_bank import model_bank

    output_dir = current_app.config['OUTPUT_DIR']
    common = {"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id,
              'series_uuid': series_uid, "modality": 'CT', "APP_OUTPUT_DIR": output_dir}

    levels = [k for k, v in model_bank.items() if 'CT' in v.keys()]
    segment_bodies = [{**common, "vertebra": level, "num_slices": "1"} for level in levels]
    _submit_pipeline(infer_spine, 'high', dict(common), segment_bodies, cleanup_ctx)


def _submit_cbct(image_path, series_dir, patient_id, series_uid, cleanup_ctx):
    from app import mongo
    from abcTK.inference.register import infer_register
    from abcTK.segment.model_bank import model_bank

    modality = 'CBCT'
    ## Query database for this patient and see if they have a planning CT labelled
    response = mongo.db.spine.find_one({"patient_id": patient_id, "all_parameters.modality": "CT"})
    if response is None:
        raise ValueError(f"Could not find a labelled CT for patient: {patient_id}")
    reference_scan = response['_id']

    ## The planning CT's own inbox copy was removed once its pipeline finished - restore it (and
    ## its RTSTRUCT, needed for calibration) from Orthanc into this CBCT's series_dir, so they're
    ## cleaned up along with it and concurrent CBCTs for the same patient never share files.
    ## Data received before inbox cleanup existed may still be on disk under its recorded path,
    ## in which case the jobs fall back to that (no override passed).
    reference = {"reference_scan": reference_scan}

    if not os.path.exists(response['input_path']):
        pct_orthanc_id = lookup_series(reference_scan)
        if pct_orthanc_id is None:
            raise ValueError(f"Planning CT ({reference_scan}) for patient {patient_id} is no longer in Orthanc - re-send it.")
        reference['reference_input_path'] = os.path.join(series_dir, 'reference', 'CT')
        fetch_series(pct_orthanc_id, reference['reference_input_path'])

    ## A missing RTSTRUCT isn't fatal here - only calibration (in the segment jobs) needs it,
    ## and they report it clearly; registration can still run.
    image_record = mongo.db.images.find_one({"_id": reference_scan}) or {}
    rtstruct_series_uuid = image_record.get('rtstruct_series_uuid')
    if rtstruct_series_uuid is not None and not os.path.isfile(image_record.get('rtstruct_path', '')):
        rtstruct_orthanc_id = lookup_series(rtstruct_series_uuid)
        if rtstruct_orthanc_id is None:
            raise ValueError(f"RTSTRUCT ({rtstruct_series_uuid}) for patient {patient_id} is no longer in Orthanc - re-send it.")
        rtstruct_dir = os.path.join(series_dir, 'reference', 'RTSTRUCT')
        fetch_series(rtstruct_orthanc_id, rtstruct_dir)
        reference['reference_rtstruct_path'] = os.path.join(rtstruct_dir, os.listdir(rtstruct_dir)[0])

    output_dir = current_app.config['OUTPUT_DIR']

    ## The CBCT and planning CT are acquired on different machines with no shared
    ## coordinate frame and no exportable registration object from MOSAIQ, so a
    ## registration job runs first to align them and correct the vertebra slice
    ## numbers before segmentation - see abcTK/inference/register.py.
    register_body = {"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id,
                     'series_uuid': series_uid, "APP_OUTPUT_DIR": output_dir, **reference}
    logger.info(f"Submitting: {register_body}")

    levels = [k for k, v in model_bank.items() if modality in v.keys()]
    segment_bodies = []
    for level in response['prediction'].keys():
        if level not in levels:
            logger.info(f"No {modality} model for {level} vertebra, not submitting job...")
            continue
        segment_bodies.append({"input_path": image_path, "project": UNASSIGNED_PROJECT, "patient_id": patient_id, "vertebra": level,
            'series_uuid': series_uid, "modality": modality, "num_slices": "1", "resample": "True",
            'calibrate_cbct': 'True', 'calibration_structure': 'brainstem', "APP_OUTPUT_DIR": output_dir, **reference})

    _submit_pipeline(infer_register, 'low', register_body, segment_bodies, cleanup_ctx)


def _record_rtstruct(image_path, study_uid, series_uid):
    ## Insert into database, so the planning CT's RTSTRUCT can be fetched back from Orthanc later
    from app import mongo
    filepath = [os.path.join(image_path, x) for x in os.listdir(image_path)]
    assert len(filepath) == 1, f"One RTSTRUCT expected. Found {len(filepath)}"
    ## rtstruct_path is kept as a "has RTSTRUCT" flag (see api/database.py) - the file itself is
    ## removed from the inbox straight away, rtstruct_series_uuid is what's used to restore it.
    update = {'$set': {'rtstruct_path': filepath[0], 'rtstruct_series_uuid': series_uid}}

    # Find the planning CT
    logger.info(f"Inserting RTSTRUCT into db. Path: {filepath[0]}")
    res = mongo.db.images.find_one({'study_uuid': study_uid, 'modality': 'CT'})

    if res is None:
        ## Fetch the reference CT uid from the header
        dcm = pydicom.dcmread(filepath[0], stop_before_pixels=True)
        try:
            ref_series_uid = str(dcm[0x3006, 0x0010].value[0][0x3006, 0x0012].value[0][0x3006, 0x0014].value[0][0x0020, 0x000e].value)
        except Exception:
            raise ValueError(f'Could not find planning CT matching RTSTRUCT with studyUID: {study_uid}.')
        mongo.db.images.update_one({'_id': ref_series_uid}, update, upsert=True)
    else:
        mongo.db.images.update_one({'_id': res['_id']}, update, upsert=True)
