"""
Endpoints for submitting jobs

"""
import dill
import requests
import logging
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
    ## Expects project
    req = request.form.to_dict()
    print(req, flush=True)
    if 'file' not in request.files:
        res = make_response(jsonify({
            "message": "Server did not receive a file",
            "data": None
        }), 400)
        return res

    f = request.files["file"]
    #f.save(secure_filename(f.filename))
    #f.stream.seek(0)
    content = ""
    for line in f.stream.readlines():
        content += line.decode("UTF-8") # Decode here as needed
    
    print(content)

    ## Read csv, expects one line per job with extra columns = args to pass

    ## Job type should be in CSV with options = [spine, segment, full]

    ### Submit the relevant jobs

    ## Send confirmation of number of jobs submitted ? List of job IDs


    res = make_response(jsonify({
        "message": "Returning failed jobs",
        "data": req
    }), 200)
    return res