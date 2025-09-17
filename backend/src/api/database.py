"""
Endpoints for interacting with database

"""
import dill
import logging
import pandas as pd
from flask import Blueprint, request, make_response, jsonify
import numpy as np
from rq import Queue
import shutil

bp = Blueprint('api/database', __name__)
logger = logging.getLogger(__name__)


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

    data = []
    for patient in patients:
        series = database.images.distinct('series_uuid', {"project": project, "patient_id": patient})
        data.append({"patient_id": patient, "series_uuids": series})

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

@bp.route('/api/database/change_project', methods=['POST'])
def change_project():
    ## Given an id in an existing project, reassign to a different project
    req = request.get_json()
    required_args = ['_id', 'current_project', 'new_project']
    assert all([x in req for x in required_args]), f"Missing some required args. Provide all of: {required_args}"

    from app import mongo
    # Update any db entries
    database = mongo.db 

    #If want to move all patients
    if req['_id'] == '*':
        logger.info(f"Moving all images in {req['current_project']} to {req['new_project']}")
        database.images.update_many({"project": req["current_project"]},
                                    {"$set": {"project": req["new_project"]}})    
        
        database.segmentation.update_many({"project": req["current_project"]},
                                {"$set": {"project": req["new_project"]}})
        
        database.spine.update_many({"project": req["current_project"]},
                                {"$set": {"project": req["new_project"]}})

        database.quality_control.update_many({"project": req["current_project"]},
                            {"$set": {"project": req["new_project"]}})
        
         # How to handle any outputs? Move to new directory? and makedirs
        all_queries = database.segmentation.find({"project": req['new_project']})
        if all_queries:
            for seg_query in all_queries:
                new_output_dir = seg_query['output_dir'].replace(req['current_project'], req['new_project'])
                logger.info(f"Updating output_directory from {seg_query['output_dir']} to {new_output_dir}")

                shutil.move(seg_query['output_dir'], new_output_dir)
            
                # Update the output path
                database.segmentation.update_one({"_id": seg_query['_id'], "project": req["new_project"]},
                                    {"$set": {"output_dir": new_output_dir}})
                

                database.spine.update_one({"_id": seg_query['_id'], "project": req["new_project"]},
                                    {"$set": {"output_dir": new_output_dir}})

        # Update the paths to sanity images
        all_queries = database.quality_control.find({"project": req['new_project']})
        if all_queries:
            for qc_query in all_queries:
                new_paths = {}
                for level, path_dict in qc_query['paths_to_sanity_images'].items():
                    if isinstance(path_dict, dict):
                        # If it's a dict, then in format: {Level: {Compartment: path}}
                        new_paths[level] = {compartment: path.replace(f"/data/outputs/{req['current_project']}", f"/data/outputs/{req['new_project']}") for compartment, path in path_dict.items()}
                    else:
                        # If it's a str, then format is: {Compartment: path}
                        new_paths[level] = path_dict.replace(f"/data/outputs/{req['current_project']}", f"/data/outputs/{req['new_project']}")

                database.quality_control.update_one({"_id": qc_query['_id'], "project": req["new_project"]},
                                    {"$set": {"paths_to_sanity_images": new_paths}})



    else:
        database.images.update_one({"_id": req['_id'], "project": req["current_project"]},
                                    {"$set": {"project": req["new_project"]}})    
        
        database.segmentation.update_one({"_id": req['_id'], "project": req["current_project"]},
                                {"$set": {"project": req["new_project"]}})
        
        database.spine.update_one({"_id": req['_id'], "project": req["current_project"]},
                                {"$set": {"project": req["new_project"]}})

        database.quality_control.update_one({"_id": req['_id'], "project": req["current_project"]},
                            {"$set": {"project": req["new_project"]}})
    
        # How to handle any outputs? Move to new directory? and makedirs
        seg_query = database.segmentation.find_one({"_id": req['_id'], "project": req['new_project']})
        if seg_query:
            new_output_dir = seg_query['output_dir'].replace(req['current_project'], req['new_project'])
            shutil.move(seg_query['output_dir'], new_output_dir)
        
            # Update the output path
            database.segmentation.update_one({"_id": req['_id'], "project": req["new_project"]},
                                {"$set": {"output_dir": new_output_dir}})
            

            database.spine.update_one({"_id": req['_id'], "project": req["new_project"]},
                                {"$set": {"output_dir": new_output_dir}})

        # Update the paths to sanity images
        qc_query = database.quality_control.find_one({"_id": req['_id'], "project": req['new_project']})
        if qc_query:
            new_paths = {}
            for level, path_dict in qc_query['paths_to_sanity_images'].items():
                if isinstance(path_dict, dict):
                    # If it's a dict, then in format: {Level: {Compartment: path}}
                    new_paths[level] = {compartment: path.replace(f"/data/outputs/{req['current_project']}", f"/data/outputs/{req['new_project']}") for compartment, path in path_dict.items()}
                else:
                    # If it's a str, then format is: {Compartment: path}
                    new_paths[level] = path_dict.replace(f"/data/outputs/{req['current_project']}", f"/data/outputs/{req['new_project']}")

            database.quality_control.update_one({"_id": req['_id'], "project": req["new_project"]},
                                {"$set": {"paths_to_sanity_images": new_paths}})
    
    res = make_response(
        jsonify({
            "message": f"Moved {req['_id']} to {req['new_project']}.",
            "request": req}),
        200)
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
