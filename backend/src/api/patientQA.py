"""
Endpoints for the patient-specific QA page
"""

import base64
import logging
from flask import Blueprint, request, make_response, jsonify, abort

from app import mongo
import abcTK.database.collections as cl
from abcTK.segment.model_bank import model_bank

bp = Blueprint('api/patient_qa', __name__)
logger = logging.getLogger(__name__)


@bp.route('/api/patient_qa/fetch_patient_list', methods=["GET"])
def fetchPatientList():
    project = request.args.get("project")
    # Figure out what image to retrieve
    vertebra = request.args.get("vertebra")
    database = mongo.db

    response = database.quality_control.find_one({f"overall_qc_state.{vertebra}": 2, 'project': project})
    cursor = database.quality_control.find(
        {'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}})
                                    
    if response is None:                                          
        ## If none to label, show errors first
        cursor = cursor.sort([f"overall_qc_state.{vertebra}"])
    else:
        cursor = cursor.sort(f"overall_qc_state.{vertebra}", -1) ## Otherwise give those todo first

    image_dict = {}
    for doc in cursor:
        pid = doc['patient_id']
        ## Get list of patient ids 
        q = database.images.find_one({'_id': doc['_id']})
        elem = {doc['_id']: q['acquisition_date']}
        if pid in image_dict:
            image_dict[pid].update(elem)
        else:
            image_dict[pid] = elem
    ## Sort each element by acquisition data (second elem of every tuple)
    #image_dict = {k: sorted(v, key=lambda x: x[1]) for k, v in image_dict.items()}


    res = make_response(jsonify({
        "message": "Here's your list of patient IDs with image IDs",
        "image_dict": image_dict
        }), 200)
    return res

@bp.route('/api/patient_qa/get_filtered_patient_list', methods=['GET'])
def getFilteredPatientList():
    ## Return list of patients and overall status -- prioritise in order: todo, fail, success
    project = request.args.get("project")
    # Figure out what image to retrieve
    vertebra = request.args.get("vertebra")
    database = mongo.db

    cursor = database.quality_control.find(
        {'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}})

    status_dict = {}
    for doc in cursor:
        pid = doc['patient_id']
        ## Get list of patient ids
        status = doc['overall_qc_state'][vertebra]

        if pid in status_dict:
            if status_dict[pid] == 2: #Never replace todo
                continue
            elif status_dict[pid] == 0: # If failed
                if status == 2: #Only replace if todo
                    status_dict[pid] = status
            else: ## Success
                if status != 1: #If not success, replace
                    status_dict[pid] = status
        else:
            status_dict[pid] = status


    output_dict = {'to-do': [], 'failed': [], 'passed': []}
    for pid, status in status_dict.items():
        if status == 2:
            output_dict['to-do'].append(pid)
        elif status == 1:
            output_dict['passed'].append(pid)
        elif status == 0:
            output_dict['failed'].append(pid)
        else:
            raise ValueError("Invalid status!") ## This should never happen...
    
    res = make_response(jsonify({
        "message": "Here's your list of patient IDs",
        "status_dict": output_dict
        }), 200)
    return res



@bp.route('/api/patient_qa/fetch_image_by_id', methods=['GET'])
def fetchImageByID():
    _id = request.args.get("_id")
    project = request.args.get("project")
    vertebra = request.args.get("vertebra")


    database = mongo.db 
    response = database.quality_control.find_one({f"_id": _id,'project': project})
    im_info = database.images.find_one({"_id": response["_id"]})

    #TODO Faster if image stored in db? Instead of loading and converting
    if vertebra in response['paths_to_sanity_images']['ALL']:
        path_to_sanity_ = response['paths_to_sanity_images']['ALL'][vertebra] 
    else:
        path_to_sanity_ = response['paths_to_sanity_images']['ALL']

    ## Compartments should come from the model_bank -- what compartments should have been segmented, not which ones were actually segmented.
    compartments = [x for x in model_bank[vertebra][im_info['modality']]['segments'].keys() if x != 'background']
    ## Add IMAT if skeletal muscle segmented
    if 'skeletal_muscle' in compartments:
        compartments.append('IMAT')

    with open(path_to_sanity_, 'rb') as f:
        image = bytearray(f.read())
    encoded_im = base64.b64encode(image).decode('utf8').replace("'",'"')

    status = response['overall_qc_state'][vertebra]

    res = make_response(jsonify({
        "message": "Here's your image",
        "image": encoded_im,
        "patient_id": response["patient_id"],
        "status": status,
        "series_uuid": im_info["series_uuid"],
        "acquisition_date": im_info["acquisition_date"],
        "input_path": im_info["input_path"],
        "vertebra": vertebra,
        "compartments": compartments
    }), 200)

    return res

@bp.route('/api/patient_qa/pass_qa', methods=['POST'])
def passQA():
    project = request.args.get("project")
    _id = request.args.get("_id")
    vertebra = request.args.get("vertebra")
    database = mongo.db 

    compartments = database.quality_control.find_one({'_id': _id, 'project': project})['quality_control'][vertebra]

    fields = [f'quality_control.{vertebra}.{compartment}' for compartment in compartments.keys()]
    payload = {field: 1 for field in fields}
    payload['overall_qc_state'] = {vertebra: 1}
    
    database.quality_control.update_one({f"_id": _id, 'project': project},#
                                         {'$set': payload })
    res = make_response(jsonify({
        "message": "QA pass recorded"
    }), 200)

    return res

@bp.route('/api/patient_qa/fail_qa_report', methods=['POST'])
def failQAReport():
    ## Get query string args
    project = request.args.get("project")
    _id = request.args.get("_id")
    vertebra = request.args.get("vertebra")

    ## Get request body
    req = request.get_json()    
    payload = {vertebra: {k: v for k, v in req.items() if v != ''} }## If not empty
    print("Received payload: ", payload, flush=True)
    # Update db
    database = mongo.db

    database.quality_control.update_one({"_id": _id}, {"$set": {"qc_report": payload}}, upsert=True)

    compartments = database.quality_control.find_one({'_id': _id, 'project': project})['quality_control'][vertebra]
    fields = [f'quality_control.{vertebra}.{compartment}' for compartment in compartments.keys()]
    #  Update qc control flag
    if payload[vertebra]["failMode"] == 'badSegmentation':
        ## Fail compartments in failedCompartments otherwise pass
        q = {field: 0 if any([x in field for x in payload[vertebra]['failedCompartments']]) else 1 for field in fields }
        q['overall_qc_state'] = {vertebra: 0}
        logger.info(f"Failed seg: {q}")
    elif payload[vertebra]["failMode"] == 'wrongLevel':
        ## Fail spine
        q = {field: 0 if 'SPINE' in field else 1 for field in fields}
        q['overall_qc_state'] = {vertebra: 0}
    else:
        ## FailMode = Other or scan Issue fail both 
        ## Fail both
        q = {field: 0 for field in fields}
        q['overall_qc_state'] = {vertebra: 0}

    database.quality_control.update_one({f"_id": _id,'project': project},  {'$set': q })

    res = make_response(jsonify({
        'message': 'Succesfully submitted report'
    }), 200)

    return res



@bp.route('/api/patient_qa/get_image_pass_rate', methods=['GET'])
def getImagePassRate():
    project = request.args.get("project")
    vertebra = request.args.get("vertebra")

    database = mongo.db
    cursor = database.quality_control.find(
        {'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}})
    
    passed = 0
    total = 0
    for doc in cursor:
        if doc['overall_qc_state'][vertebra] == 1:
            passed += 1
            total += 1
        else:
            total += 1
    pass_rate = 100*(passed/total)

    res = make_response(jsonify({
        'message': f'Pass rate for project ({project}) at level ({vertebra}) is: {pass_rate}',
        'passed': passed,
        'total': total,
        'pass_rate': round(pass_rate, 1)
    }), 200)

    return res