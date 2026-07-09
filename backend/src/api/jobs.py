"""
Endpoints for submitting jobs

"""
import dill
import requests
import logging
import pandas as pd
from flask import Blueprint, request, make_response, jsonify, current_app
from rq import Queue
from rq.job import Job
from rq.registry import FailedJobRegistry
from werkzeug.utils import secure_filename

bp = Blueprint('api/jobs', __name__)
logger = logging.getLogger(__name__)


@bp.route('/api/jobs/infer/spine', methods=["POST"])
def queue_infer_spine():
    req = request.get_json()

    req['APP_OUTPUT_DIR'] = current_app.config['OUTPUT_DIR']
    from app import redis
    from abcTK.inference.spine import infer_spine
    
    # Sent to high queue for processing by GPU worker
    q = Queue('high', connection=redis, serializer=dill)
    job = q.enqueue(infer_spine, req, job_timeout=300)

    res = make_response(jsonify({
            "message": "Spine inference submitted",
            "request": req,
            "job-ID": job.id})
            , 200)
    return res


@bp.route('/api/jobs/infer/segment', methods=["POST"])
def queue_infer_segment():
    req = request.get_json()
    if 'depends_on' not in req:
        req['depends_on'] = None
    print(f"----- Job depends on job-id: {req['depends_on']} -----", flush=True)
    
    req['APP_OUTPUT_DIR'] = current_app.config['OUTPUT_DIR']
    from app import redis
    from abcTK.inference.segment import infer_segment
    q = Queue('default', connection=redis, serializer=dill) # Sent to default queue

    if 'vertebra' not in req:
        
        # Check all available models in model bank
        from abcTK.segment.model_bank import model_bank
        levels = [k for k, v in model_bank.items() if req['modality'] in v.keys()]
        logger.warn(f"No vertebra specified, attempting to segment the following: {levels}")
        jobs = []
        for level in levels:
            req['vertebra'] = level
            job = q.enqueue(infer_segment, req, depends_on=req['depends_on'])
            jobs.append(job.id)
        res = make_response(jsonify({
                "message": "Segmentation inference submitted",
                "request": req,
                "level": levels,
                "job-ID": jobs})
                , 200)
    else:
        job = q.enqueue(infer_segment, req, depends_on=req['depends_on'])

        res = make_response(jsonify({
                "message": "Segmentation inference submitted",
                "request": req,
                "level": req['vertebra'], 
                "job-ID": job.id})
                , 200)
    return res


@bp.route('/api/jobs/query_job', methods=["GET"])
def query_job():
    from app import redis
    #TODO Return job status + outputs given a job id
    job_id = request.args.get("id")

    job = Job.fetch(id=job_id, connection=redis)
    result = job.latest_result()
    
    res = make_response(jsonify({
        'job-ID': job_id,
        'status': str(result.type),
        "result": str(result.return_value) if result.type == "Type.SUCCESSFUL" else result.exc_string
    }), 200)

    return res

@bp.route('/api/jobs/get_failed_jobs', methods=["GET"])
def get_failed_jobs():
    project = request.args.get("project")

    from app import redis

    queue = Queue('high', connection=redis)
    registry = FailedJobRegistry(queue=queue)

    data = {}
    for job_id in registry.get_job_ids():
        job = Job.fetch(job_id, connection=redis)
        print(job.args)
        if project is not None and job.args[0]['project'] == project:
            print('Found job from selected project', flush=True)
            print(job_id, job.exc_info, flush=True)
            data[job_id] = {'args': job.args[0], 'error': job.exc_info}

    res = make_response(jsonify({
        "message": "Returning failed jobs",
        "data": data
    }), 200)
    return res


@bp.route('/api/jobs/submit_jobs_from_csv', methods=['POST'])
def submit_jobs_from_csv():
    """
    Submit a batch of spine/segment jobs from an uploaded CSV (multipart/form-data).

    Form fields:
      - "project": project name applied to every row, unless a row's own "project" column overrides it.
      - "file": the CSV. One row per scan. Required column: "input_path" (in-container path to the
        scan). Optional column: "job_type" - one of "spine", "segment", "full" (default "full" -
        submits a spine job followed by a dependent segment job, mirroring the two-step pipeline
        documented in docs/api-reference.md). Every other column is passed straight through as an
        extra request argument for that row (e.g. "vertebra", "num_slices", "patient_id",
        "worldmatch_correction") - same argument names as /api/jobs/infer/spine and
        /api/jobs/infer/segment.
    """
    project = request.form.get('project')
    if not project:
        raise ValueError("Missing required form field: 'project'")

    if 'file' not in request.files:
        raise ValueError("No CSV file was uploaded. Attach it under the 'file' form field.")

    f = request.files['file']
    try:
        df = pd.read_csv(f.stream)
    except Exception as e:
        raise ValueError(f"Could not parse the uploaded file as CSV: {e}")

    if 'input_path' not in df.columns:
        raise ValueError("CSV is missing the required 'input_path' column.")

    from app import redis
    from abcTK.inference.spine import infer_spine
    from abcTK.inference.segment import infer_segment

    output_dir = current_app.config['OUTPUT_DIR']
    spine_queue = Queue('high', connection=redis, serializer=dill)
    segment_queue = Queue('default', connection=redis, serializer=dill)

    submitted = []
    for i, row in df.iterrows():
        # CSV cells come back as numpy/pandas scalar types (int64, bool, ...); the inference
        # request parsers (abcTK/inference/{spine,segment}.py::handle_request) expect plain
        # strings, same as every other request body in this API - convert to match.
        row_args = {k: str(v) for k, v in row.to_dict().items() if pd.notna(v)}
        job_type = row_args.pop('job_type', 'full').lower()
        row_project = row_args.pop('project', project)

        if job_type not in ('spine', 'segment', 'full'):
            submitted.append({"row": int(i), "error": f"Unrecognised job_type '{job_type}' — must be spine, segment, or full"})
            continue

        entry = {"row": int(i), "input_path": row_args.get('input_path')}

        spine_job = None
        if job_type in ('spine', 'full'):
            spine_body = {**row_args, "project": row_project, "APP_OUTPUT_DIR": output_dir}
            spine_job = spine_queue.enqueue(infer_spine, spine_body, job_timeout=300)
            entry["spine_job_id"] = spine_job.id

        if job_type in ('segment', 'full'):
            segment_body = {**row_args, "project": row_project, "APP_OUTPUT_DIR": output_dir}
            depends_on = spine_job.id if spine_job is not None else None
            segment_job = segment_queue.enqueue(infer_segment, segment_body, depends_on=depends_on)
            entry["segment_job_id"] = segment_job.id

        submitted.append(entry)

    res = make_response(jsonify({
        "message": f"Submitted jobs for {len(submitted)} row(s)",
        "jobs": submitted
    }), 200)
    return res