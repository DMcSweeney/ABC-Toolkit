"""
Endpoints for interacting with database

"""
import dill
import datetime
import logging
import os
import re
import pandas as pd
from flask import Blueprint, request, make_response, jsonify, current_app
import numpy as np
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry
import shutil

from abcTK.constants import UNASSIGNED_PROJECT

bp = Blueprint('api/database', __name__)
logger = logging.getLogger(__name__)

# Project names flow into os.path.join()/shutil.move() destinations, and (via the CSV
# assignment endpoint) can originate from untrusted file content rather than a value a
# human typed into a validated form field - so validate server-side too.
PROJECT_NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')

# RQ queues jobs can be enqueued on (see api/jobs.py) - checked for in-flight work before
# reassigning a patient, since a running spine/segment job recomputes output_dir from its
# own captured request and would otherwise resurrect the old project's directory/project
# field after a move (abcTK/inference/segment.py & spine.py::update_database).
JOB_QUEUE_NAMES = ['high', 'default', 'low']


@bp.route('/api/database/delete_entry', methods=["POST"])
def delete_entry():
    req = request.get_json()
    _id = req['_id']
    coll = req['collection']
    
    from app import mongo

    database = mongo.db
    database[coll].delete_one({"_id": _id})

    res = make_response(jsonify({
        'message': f'Succesfully deleted entry {_id} in {coll}'
    }), 200)

    return res


@bp.route('/api/database/get_qc_report', methods=['GET'])
def get_gc_report():
    from app import mongo
    database = mongo.db
    project = request.args.get("project")
    _id = request.args.get("_id", None)
    if _id is not None:
        # Filter on project and _id and non-empty qc_report
        cursor = database.quality_control.find({"project": project, "_id": _id, "qc_report": {"$ne": {}} }, {"series_uuid": 1, "qc_report": 1})
        message = f'Found report for _id ({_id})'
    else:
        cursor = database.quality_control.find({"project": project, "qc_report": {"$ne": {}} }, {"series_uuid": 1, "qc_report": 1})
    
    reports = [(x['series_uuid'], x['qc_report']) for x in cursor]
    message = f'Found {len(reports)} non-empty qc reports for project ({project})'

    if len(reports) == 0:
        res = make_response(jsonify({
            'message': "Could not find any reports",
            "reports": None,
            }), 200)
    else:
        res = make_response(jsonify({
            'message': message,
            "reports": reports
        }), 200)

    return res


@bp.route('/api/database/get_project_info', methods=["GET"])
def get_project_info():
    """
    Endpoint for fetching list of dicts with project info
    """

    # Don't expect anything in request
    from app import mongo
    database = mongo.db

    # Get unique project names
    projects = database.images.distinct("project")
    # Get # patients and images per project
    data = []
    for project in projects:
        patients = database.images.distinct("patient_id", {"project": project})
        images = database.images.distinct("series_uuid", {"project": project})
        data.append({'name': project, 'num_patients': len(patients), "num_images": len(images)})

    res = make_response(jsonify({
        "message": "Successfully retrieved project info",
        "data": data,
    }), 200)
    return res

@bp.route('/api/database/get_patients_in_project', methods=["GET"])
def get_patients_in_project():
    project = request.args.get("project")
    from app import mongo   
    database = mongo.db

    patients = database.images.distinct('patient_id', {"project": project})

    data = {x: {} for x in patients}
    for patient in patients:
        series = database.images.distinct('series_uuid', {"project": project, "patient_id": patient})
        vertebrae = set()
        rtstruct = False
        for uuid in series:
            q = database.images.find_one({'_id': uuid})
            if q is not None and 'rtstruct_path' in q:
                rtstruct = True
            preds = database.spine.find_one({'_id': uuid})
            if preds is None:
                continue
            pred_levels = set(list(preds['prediction'].keys()))
            vertebrae  = vertebrae | pred_levels
        data[patient] = {'num_series': len(series), 
                         'vertebrae': ', '.join([x for x in sorted(list(vertebrae))]), 
                         'rtstruct_detected': 'detected' if rtstruct else 'not detected'}
    logger.info(data)
    res = make_response(jsonify({
        "message": "Data is list of dicts. Keys: patient_id, series_uuids",
        "data": data
    }), 200)
    return res

@bp.route('/api/database/get_levels_to_QA', methods=["GET"])
def get_levels_to_QA():
    #TODO This needs to be finished 
    project = request.args.get("project")
    from app import mongo   
    database = mongo.db

    def gather_from_segmentation_db():
        uuids = database.segmentation.distinct('series_uuid', {"project": project})
        
        data = []
        for uuid in uuids:
            levels = database.segmentation.find_one({"project": project, "series_uuid": uuid}, {'statistics': 1})
            data.extend(list(levels['statistics'].keys()))
        return set(data)

    unique_levels= list(gather_from_segmentation_db())

    res = make_response(jsonify({
        "message":f"{len(unique_levels)} unique vertebrae detected in project",
        "data": unique_levels
    }), 200)
    return res


@bp.route('/api/database/get_patient_filter_options', methods=["GET"])
def get_patient_filter_options():
    """
    List every (vertebra, compartment, modality) combination this patient actually has
    completed segmentation data for, so the frontend can build filter dropdowns from real
    data instead of a hardcoded list. Compartment options are read strictly from the literal
    keys stored in `statistics` -- deliberately NOT synthesizing an 'IMAT' option the way
    patientQA.py's model_bank-driven compartment list does (that rule doesn't check modality
    and may offer IMAT as an option even where it was never actually computed, e.g. for CBCT).
    """
    project = request.args.get("project")
    patient_id = request.args.get("patient_id")
    from app import mongo
    database = mongo.db

    docs = database.segmentation.find({"project": project, "patient_id": patient_id}, {'statistics': 1, 'series_uuid': 1})

    def parse_date(date_str):
        try:
            return datetime.datetime.strptime(date_str, "%d-%m-%Y")
        except (ValueError, TypeError):
            return datetime.datetime.min

    # Keyed by (vertebra, compartment, modality) -> most-recent acquisition_date seen for that combo
    combos = {}
    for doc in docs:
        img = database.images.find_one({'_id': doc['_id'], 'project': project}, {'modality': 1, 'acquisition_date': 1})
        if img is None:
            continue
        modality = img.get('modality')
        acquisition_date = img.get('acquisition_date')

        for level_key, compartments in doc.get('statistics', {}).items():
            vertebra = level_key.replace('-edited', '').replace('-manual', '')
            for compartment in compartments.keys():
                key = (vertebra, compartment, modality)
                if key not in combos or parse_date(acquisition_date) > parse_date(combos[key]):
                    combos[key] = acquisition_date

    data = [{"vertebra": v, "compartment": c, "modality": m, "acquisition_date": d}
            for (v, c, m), d in combos.items()]

    res = make_response(jsonify({
        "message": f"Found {len(data)} filter combinations for {patient_id}",
        "data": data
    }), 200)
    return res


@bp.route('/api/database/get_labelling_status', methods=["GET"])
def get_labelling_status():
    ## Collect patients and uuids with labelling done / to-do
    project = request.args.get("project")
    level = request.args.get("level", None)
    from app import mongo   
    database = mongo.db

    exists = database.images.find({'project': project})
 
    if exists:
        uuids = database.images.distinct('series_uuid', {"project": project})
        data = []
        for uuid in uuids:
            entry = list(database.images.find({"project": project,"series_uuid": uuid}))[0]
            if bool(entry['labelling_done']) and level is not None:
                pred = list(database.spine.find({'project': project, "series_uuid": uuid}))
                if pred: # If not empty
                    levels = [x for x in pred[0]['prediction'].keys()]
                    status = level in levels   
                else:
                    print(f'------ NO ENTRY IN SPINE DB --- {entry["patient_id"]}')
                    continue
            else:
                status = bool(entry['labelling_done'])
            
            data.append({'patient_id': entry['patient_id'], 'input_path':entry['input_path'], 'series_uuid': uuid,  'status': status})

    if level is not None:
        output_filename=f'/data/outputs/labelling_status_{level}_{project}.csv'
    else:
        output_filename=f'/data/outputs/labelling_status_{project}.csv'

    df = pd.DataFrame(data)
    df.to_csv(output_filename)

    # Return number pass fail
    passed = np.sum([bool(x['status']) for x in data])
    res = make_response(jsonify({
        "message": "Successfully collected labelling status",
        "% passed": (passed/len(data))*100
    }), 200)
    return res

@bp.route('/api/database/get_segmentation_status')
def get_segmentation_status():
    ## Collect patients and uuids with labelling done / to-do
    project = request.args.get("project")
    from app import mongo   
    database = mongo.db

    exists = database.images.find({'project': project})
 
    if exists:
        uuids = database.images.distinct('series_uuid', {"project": project})
        data = []
        for uuid in uuids:
            entry = list(database.images.find({"project": project,"series_uuid": uuid}))[0]
            status = bool(entry['segmentation_done'])
            
            data.append({'series_uuid': uuid, 'patient_id': entry['patient_id'], 'status': status})


    output_filename=f'/data/outputs/segmentation_status_{project}.csv'

    df = pd.DataFrame(data)
    df.to_csv(output_filename)

    # Return number pass fail
    passed = np.sum([bool(x['status']) for x in data])
    res = make_response(jsonify({
        "message": "Successfully collected segmentation status",
        "% passed": (passed/len(data))*100
    }), 200)
    return res

@bp.route('/api/database/get_input_args', methods=["GET"])
def get_input_args():
    from app import mongo
    database = mongo.db
    project = request.args.get("project")
    _id = request.args.get("_id", None)

    entry = database.images.find_one({"_id": _id, "project": project})

    res = make_response(jsonify({
        "message": f"Successfully collected input arguments for {_id}",
        "data": entry
    }), 200)
    return res


@bp.route('/api/database/get_spine_entry', methods=["GET"])
def get_spine_entry():
    from app import mongo
    database = mongo.db
    project = request.args.get("project")
    _id = request.args.get("_id", None)

    entry = database.spine.find_one({"_id": _id, "project": project})

    res = make_response(jsonify({
        "message": f"Successfully collected spine database entry",
        "data": entry
    }), 200)
    return res

@bp.route('/api/database/extract_stats_from_mask', methods=["POST"])
def extract_stats_from_mask():
    ## Needs _id, project and path to new mask
    req = request.get_json()
    
    from app import redis
    from abcTK.segment.extract_stats import extract_stats

    q = Queue('default', connection=redis, serializer=dill)    
    job = q.enqueue(extract_stats, req, job_timeout=300)
    
    
    res = make_response(jsonify({
            "message": "Spine inference submitted",
            "request": req,
            "job-ID": job.id})
            , 200)
    return res

def _reassign_documents(database, output_base_dir, filter_query, current_project, new_project):
    """
    Move every document matching filter_query (which must already scope to
    current_project - e.g. {"project": current_project} for a whole-project move, or with
    an added "_id"/"patient_id" key to scope to a subset) into new_project, across all 4
    collections, then move the corresponding on-disk output directories/sanity-image paths
    to match.
    """
    update = {"$set": {"project": new_project}}
    database.images.update_many(filter_query, update)
    database.segmentation.update_many(filter_query, update)
    database.spine.update_many(filter_query, update)
    database.quality_control.update_many(filter_query, update)

    # Re-query under the new project to find exactly what was just moved.
    moved_filter = {**filter_query, "project": new_project}

    for seg_query in database.segmentation.find(moved_filter):
        # Rebuilt from known fields rather than string-replacing current_project inside
        # the old output_dir - that substring isn't anchored to a path boundary, so it
        # can corrupt the path if a patient_id/series_uuid happens to contain it.
        new_output_dir = os.path.join(output_base_dir, new_project, seg_query['patient_id'], seg_query['series_uuid'])
        old_output_dir = seg_query.get('output_dir')
        if old_output_dir and old_output_dir != new_output_dir and os.path.isdir(old_output_dir):
            logger.info(f"Updating output_directory from {old_output_dir} to {new_output_dir}")
            os.makedirs(os.path.dirname(new_output_dir), exist_ok=True)
            shutil.move(old_output_dir, new_output_dir)

        database.segmentation.update_one({"_id": seg_query['_id']}, {"$set": {"output_dir": new_output_dir}})
        database.spine.update_one({"_id": seg_query['_id'], "project": new_project}, {"$set": {"output_dir": new_output_dir}})

    # Update the paths to sanity images. This prefix is anchored to a full path segment
    # (unlike the output_dir case above) so a plain replace is safe here.
    old_prefix = os.path.join(output_base_dir, current_project)
    new_prefix = os.path.join(output_base_dir, new_project)
    for qc_query in database.quality_control.find(moved_filter):
        new_paths = {}
        for level, path_dict in qc_query['paths_to_sanity_images'].items():
            if isinstance(path_dict, dict):
                # If it's a dict, then in format: {Level: {Compartment: path}}
                new_paths[level] = {compartment: path.replace(old_prefix, new_prefix) for compartment, path in path_dict.items()}
            else:
                # If it's a str, then format is: {Compartment: path}
                new_paths[level] = path_dict.replace(old_prefix, new_prefix)

        database.quality_control.update_one({"_id": qc_query['_id']}, {"$set": {"paths_to_sanity_images": new_paths}})


def _patient_has_pending_jobs(patient_id):
    """
    True if patient_id appears in the args of any queued or currently-running RQ job.
    Reassigning a patient while a spine/segment job for them is still in flight is unsafe:
    abcTK/inference/{spine,segment}.py::update_database recomputes output_dir from the
    job's own captured request (not the current Mongo state) and unconditionally
    (re)creates it, so a job finishing after a move can silently resurrect the old
    project's directory and revert the project field on some collections but not others.
    """
    from app import redis

    for queue_name in JOB_QUEUE_NAMES:
        queue = Queue(queue_name, connection=redis)
        job_ids = set(queue.job_ids) | set(StartedJobRegistry(queue=queue).get_job_ids())
        for job_id in job_ids:
            try:
                job = Job.fetch(job_id, connection=redis)
            except Exception:
                continue
            if job.args and isinstance(job.args[0], dict) and job.args[0].get('patient_id') == patient_id:
                return True
    return False


def _valid_project_name(name):
    return bool(name) and bool(PROJECT_NAME_RE.match(name))


@bp.route('/api/database/change_project', methods=['POST'])
def change_project():
    ## Given an id in an existing project, reassign to a different project
    req = request.get_json()
    required_args = ['_id', 'current_project', 'new_project']
    assert all([x in req for x in required_args]), f"Missing some required args. Provide all of: {required_args}"

    from app import mongo
    database = mongo.db
    output_base_dir = current_app.config['OUTPUT_DIR']

    #If want to move all patients
    if req['_id'] == '*':
        logger.info(f"Moving all images in {req['current_project']} to {req['new_project']}")
        filter_query = {"project": req['current_project']}
    else:
        filter_query = {"_id": req['_id'], "project": req['current_project']}

    _reassign_documents(database, output_base_dir, filter_query, req['current_project'], req['new_project'])

    res = make_response(
        jsonify({
            "message": f"Moved {req['_id']} to {req['new_project']}.",
            "request": req}),
        200)
    return res


@bp.route('/api/database/find_patient', methods=['GET'])
def find_patient():
    """
    Cross-project lookup by patient_id - deliberately not scoped to a single project,
    since the point is finding data that may be sitting in the Unassigned project or
    already split across others.
    """
    patient_id = request.args.get('patient_id')
    if not patient_id:
        raise ValueError("Missing required query param: 'patient_id'")

    from app import mongo
    database = mongo.db

    docs = list(database.images.find(
        {"patient_id": patient_id},
        {"project": 1, "series_uuid": 1, "modality": 1, "acquisition_date": 1}
    ))

    projects = {}
    for doc in docs:
        projects.setdefault(doc['project'], []).append({
            "_id": doc['_id'],
            "series_uuid": doc.get('series_uuid'),
            "modality": doc.get('modality'),
            "acquisition_date": doc.get('acquisition_date'),
        })

    data = [{"project": project, "series": series} for project, series in projects.items()]

    res = make_response(jsonify({
        "message": f"Found {len(docs)} series for patient {patient_id} across {len(data)} project(s)",
        "patient_id": patient_id,
        "projects": data,
    }), 200)
    return res


@bp.route('/api/database/reassign_patient', methods=['POST'])
def reassign_patient():
    """
    Move every series belonging to a single patient (within one current project) to a
    different project. Used by the "Assign to Project" UI - both the single-patient search
    flow and (per-row) the CSV batch flow call this same logic.
    """
    req = request.get_json()
    required_args = ['patient_id', 'current_project', 'new_project']
    assert all([x in req for x in required_args]), f"Missing some required args. Provide all of: {required_args}"

    if not _valid_project_name(req['new_project']) or not _valid_project_name(req['current_project']):
        raise ValueError("Project names may only contain letters, numbers, underscores and hyphens.")

    if _patient_has_pending_jobs(req['patient_id']):
        res = make_response(jsonify({
            "message": f"Patient {req['patient_id']} has jobs queued or in progress - try again once they finish.",
            "skipped": True,
        }), 409)
        return res

    from app import mongo
    database = mongo.db
    output_base_dir = current_app.config['OUTPUT_DIR']

    filter_query = {"patient_id": req['patient_id'], "project": req['current_project']}
    moved = database.images.distinct('series_uuid', filter_query)

    _reassign_documents(database, output_base_dir, filter_query, req['current_project'], req['new_project'])

    res = make_response(jsonify({
        "message": f"Moved {len(moved)} series for patient {req['patient_id']} from {req['current_project']} to {req['new_project']}.",
        "series_uuids": moved,
    }), 200)
    return res


@bp.route('/api/database/assign_patients_from_csv', methods=['POST'])
def assign_patients_from_csv():
    """
    Bulk-reassign patients to a project from an uploaded CSV (multipart/form-data).

    Form fields:
      - "current_project": default project rows are moved FROM, unless a row's own
        "current_project" column overrides it. Defaults to the Unassigned project.
      - "new_project": project rows are moved TO, unless a row's own "new_project" column
        overrides it.
      - "file": the CSV. One row per patient. Required column: "patient_id".
    """
    default_current_project = request.form.get('current_project') or UNASSIGNED_PROJECT
    default_new_project = request.form.get('new_project')

    if 'file' not in request.files:
        raise ValueError("No CSV file was uploaded. Attach it under the 'file' form field.")

    f = request.files['file']
    try:
        df = pd.read_csv(f.stream)
    except Exception as e:
        raise ValueError(f"Could not parse the uploaded file as CSV: {e}")

    if 'patient_id' not in df.columns:
        raise ValueError("CSV is missing the required 'patient_id' column.")

    if not default_new_project and 'new_project' not in df.columns:
        raise ValueError("Missing required form field: 'new_project' (or provide a 'new_project' column in the CSV).")

    from app import mongo
    database = mongo.db
    output_base_dir = current_app.config['OUTPUT_DIR']

    results = []
    for i, row in df.iterrows():
        row_args = {k: str(v) for k, v in row.to_dict().items() if pd.notna(v)}
        patient_id = row_args.get('patient_id')
        current_project = row_args.get('current_project', default_current_project)
        new_project = row_args.get('new_project', default_new_project)

        if not patient_id:
            results.append({"row": int(i), "error": "Missing patient_id"})
            continue

        if not _valid_project_name(new_project) or not _valid_project_name(current_project):
            results.append({"row": int(i), "patient_id": patient_id, "error": "Project names may only contain letters, numbers, underscores and hyphens."})
            continue

        if _patient_has_pending_jobs(patient_id):
            results.append({"row": int(i), "patient_id": patient_id, "error": "Patient has jobs queued or in progress - skipped."})
            continue

        filter_query = {"patient_id": patient_id, "project": current_project}
        moved = database.images.distinct('series_uuid', filter_query)
        if not moved:
            results.append({"row": int(i), "patient_id": patient_id, "error": f"No series found for patient in project '{current_project}'."})
            continue

        _reassign_documents(database, output_base_dir, filter_query, current_project, new_project)
        results.append({"row": int(i), "patient_id": patient_id, "moved_series": moved, "new_project": new_project})

    res = make_response(jsonify({
        "message": f"Processed {len(results)} row(s)",
        "results": results,
    }), 200)
    return res


@bp.route('/api/database/change_patient_id', methods=['POST'])
def change_patient_id():
    ## Given an id in an existing project, reassign to a different project
    req = request.get_json()
    required_args = ['_id', 'current_patient_id', 'new_patient_id']
    assert all([x in req for x in required_args]), f"Missing some required args. Provide all of: {required_args}"

    from app import mongo
    # Update any db entries
    database = mongo.db 

    database.images.update_one({"_id": req['_id']},
                                    {"$set": {"patient_id": req["new_patient_id"]}})    
        
    database.segmentation.update_one({"_id": req['_id']},
                            {"$set": {"patient_id": req["new_patient_id"]}})
    
    database.spine.update_one({"_id": req['_id']},
                            {"$set": {"patient_id": req["new_patient_id"]}})

    database.quality_control.update_one({"_id": req['_id']},
                        {"$set": {"patient_id": req["new_patient_id"]}})

    # How to handle any outputs? Move to new directory? and makedirs
    seg_query = database.segmentation.find_one({"_id": req['_id']})
    if seg_query:
        new_output_dir = seg_query['output_dir'].replace(req['current_patient_id'], req['new_patient_id'])
        shutil.move(seg_query['output_dir'], new_output_dir)
    
        # Update the output path
        database.segmentation.update_one({"_id": req['_id']},
                            {"$set": {"output_dir": new_output_dir}})
        

        database.spine.update_one({"_id": req['_id']},
                            {"$set": {"output_dir": new_output_dir}})

    # Update the paths to sanity images
    qc_query = database.quality_control.find_one({"_id": req['_id']})
    if qc_query:
        new_paths = {}
        for level, path_dict in qc_query['paths_to_sanity_images'].items():
            if isinstance(path_dict, dict):
                # If it's a dict, then in format: {Level: {Compartment: path}}
                new_paths[level] = {compartment: path.replace(f"/data/outputs/{qc_query['project']}/{req['current_patient_id']}",
                 f"/data/outputs/{qc_query['project']}/{req['new_patient_id']}") for compartment, path in path_dict.items()}
            else:
                # If it's a str, then format is: {Compartment: path}
                new_paths[level] = path_dict.replace(f"/data/outputs/{qc_query['project']}/{req['current_patient_id']}",
                 f"/data/outputs/{qc_query['project']}/{req['new_patient_id']}")

        database.quality_control.update_one({"_id": req['_id']},
                            {"$set": {"paths_to_sanity_images": new_paths}})
    
    res = make_response(
        jsonify({
            "message": f"Updated {req['_id']} patient_id from {req['current_patient_id']} to {req['new_patient_id']}.",
            "request": req}),
        200)
    return res


@bp.route('/api/database/upload_sanity_to_web', methods=['POST'])
def upload_sanity_to_web():
    req = request.get_json()


    ## Add patient to database and update path to sanity

    
    
    ...
