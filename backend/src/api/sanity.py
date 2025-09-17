"""
Script with sanity checking endpoints
"""
import base64
import logging
from flask import Blueprint, request, make_response, jsonify, abort
from app import mongo

import abcTK.database.collections as cl
from random import shuffle

bp = Blueprint('api/sanity', __name__)
logger = logging.getLogger(__name__)

@bp.route('/api/sanity/fetch_first_image', methods=["POST"])
def fetchFirstImage():#
    project = request.args.get("project")

    ## Figure out what image to retrieve
    vertebra =request.args.get("vertebra")
    database = mongo.db 
    response = list(database.quality_control.aggregate([
        {"$match": {f"quality_control.{vertebra}": 2, 'project': project}},
        {"$sample": {"size": 1}}
        ]))
    if not response: ## If empty list
        ## If none to label, just show failures
        response = database.quality_control.find_one({
        f"quality_control.{vertebra}": 0, 'project': project
        })
        if response is None:
            ## If no fails
            response = database.quality_control.find_one({
            f"quality_control.{vertebra}": 1, 'project': project
            })

            if response is None:
                res = make_response(jsonify({
                "message": f"No {vertebra} predictions found in {project}",
            }), 400)
            return res
    else:
        response = response[0]

    im_info = database.images.find_one({"_id": response["_id"]})

    #TODO Faster if image stored in db? Instead of loading and converting
    if vertebra in response['paths_to_sanity_images']['ALL']:
        path_to_sanity_ = response['paths_to_sanity_images']['ALL'][vertebra] 
    else:
        path_to_sanity_ = response['paths_to_sanity_images']['ALL']
    with open(path_to_sanity_, 'rb') as f:
        image = bytearray(f.read())
    encoded_im = base64.b64encode(image).decode('utf8').replace("'",'"')


    res = make_response(jsonify({
        "message": "Here's your image",
        "image": encoded_im,
        "patient_id": response["patient_id"],
        "status": response["quality_control"][vertebra],
        "series_uuid": im_info["series_uuid"],
        "acquisition_date": im_info["acquisition_date"],
        "input_path": im_info["input_path"],
        "vertebra": vertebra
    }), 200)

    return res


@bp.route('/api/sanity/fetch_image_by_id', methods=["POST"])
def fetchImageByID():
    _id = request.args.get("_id")
    project = request.args.get("project")
    vertebra = request.args.get("vertebra")
    database = mongo.db 
    response = database.quality_control.find_one({f"_id": _id,'project': project})
    im_info = database.images.find_one({"_id": response["_id"]})
    print(response, im_info, flush=True)
    #TODO Faster if image stored in db? Instead of loading and converting
    if vertebra in response['paths_to_sanity_images']['ALL']:
        path_to_sanity_ = response['paths_to_sanity_images']['ALL'][vertebra] 
    else:
        path_to_sanity_ = response['paths_to_sanity_images']['ALL']
    with open(path_to_sanity_, 'rb') as f:
        image = bytearray(f.read())
    encoded_im = base64.b64encode(image).decode('utf8').replace("'",'"')
    if "SPINE" in response["quality_control"]:
        if response["quality_control"]["SPINE"] == 2 or response["quality_control"][vertebra] == 2:
            status = 2
        elif response["quality_control"]["SPINE"] == 0 or response["quality_control"][vertebra] == 0:
            status = 0
        elif response["quality_control"]["SPINE"] == 1 and response["quality_control"][vertebra] == 1:
            status = 1
        else:
            status = 2
    else:
        # If spine labelling wasn't performed
        status = response["quality_control"][vertebra]
        

    res = make_response(jsonify({
        "message": "Here's your image",
        "image": encoded_im,
        "patient_id": response["patient_id"],
        "status": status,
        "series_uuid": im_info["series_uuid"],
        "acquisition_date": im_info["acquisition_date"],
        "input_path": im_info["input_path"],
        "vertebra": vertebra
    }), 200)

    return res

@bp.route('/api/sanity/fetch_patient_list', methods=["GET"])
def fetchPatientList():
    project = request.args.get("project")
    # Figure out what image to retrieve
    vertebra = request.args.get("vertebra")

    database = mongo.db

    response = database.quality_control.find_one({f"quality_control.{vertebra}": 2, 'project': project})
    cursor = database.quality_control.find(
        {'project': project, f"quality_control.{vertebra}": {"$exists": True}})
    
    if response is None:
        ## If none to label, show errors first
        cursor = cursor.sort([f"quality_control.{vertebra}", "quality_control.SPINE"])
    else:
        cursor = cursor.sort(f"quality_control.{vertebra}", -1)
    
    image_dict = {}
    for doc in cursor:
        pid = doc['patient_id']
        ## Get list of patient ids 
        if doc['patient_id'] in image_dict:
            image_dict[pid].append(doc['_id'])
        else:
            image_dict[pid] = [doc['_id']]
    logger.info(f'-------IMAGE DICT: {image_dict} -------------')
    res = make_response(jsonify({
        "message": "Here's your list of patient IDs",
        "image_dict": image_dict
    }), 200)
    return res
    
@bp.route('/api/sanity/fetch_image_list', methods=["POST"])
def fetchImageList():
    project = request.args.get("project")
    # Figure out what image to retrieve
    vertebra = request.args.get("vertebra")
    database = mongo.db

    response = database.quality_control.find_one({f"quality_control.{vertebra}": 2, 'project': project})
    cursor = database.quality_control.find(
        {'project': project, f"quality_control.{vertebra}": {"$exists": True}},
        {'_id': 1, f'quality_control.{vertebra}': 1}
        )
    
    if response is None:
        ## If none to label, show errors first
        #cursor = cursor.sort(f"quality_control.SPINE")
        #cursor = cursor.sort(f"quality_control.{vertebra}")
        cursor = cursor.sort([f"quality_control.{vertebra}", "quality_control.SPINE"])
    else:
        cursor = cursor.sort(f"quality_control.{vertebra}", -1)
    #TODO There must be a better way to do this?
    ids = []
    for doc in cursor:
        ids.append(doc['_id'])
    shuffle(ids)
    res = make_response(jsonify({
        "message": "Here's your list of IDs",
        "id_list": ids
    }), 200)
    return res

@bp.route('/api/sanity/fetch_spine_by_id', methods=["POST"])
def fetchSpineByID():
    _id = request.args.get("_id")
    project = request.args.get("project")
    vertebra = request.args.get("vertebra")
    database = mongo.db 
    response = database.quality_control.find_one({f"_id": _id, 'project': project})
    logger.info(response['paths_to_sanity_images']['SPINE'])
    path_to_sanity_ = response['paths_to_sanity_images']['SPINE']
    if isinstance(path_to_sanity_, dict):
        ## If dict_, spine image was generated for a single level
        path_to_sanity_ = path_to_sanity_[vertebra]

    with open(path_to_sanity_, 'rb') as f:
        image = bytearray(f.read())
    encoded_im = base64.b64encode(image).decode('utf8').replace("'",'"')

    res = make_response(jsonify({
        "message": "Here's your image",
        "image": encoded_im,
        "patient_id": response["patient_id"],
    }), 200)

    return res

@bp.route('/api/sanity/pass_qa', methods=["POST"])
def pass_qa():
    project = request.args.get("project")
    _id = request.args.get("_id")
    vertebra = request.args.get("vertebra")
    database = mongo.db 
    database.quality_control.update_one({f"_id": _id, 'project': project}, {'$set': {f'quality_control.{vertebra}': 1, 'quality_control.SPINE': 1} })

    res = make_response(jsonify({
        "message": "QA pass recorded"
    }), 200)

    return res


@bp.route('/api/sanity/fail_qa', methods=["POST"])
def fail_qa():
    project = request.args.get("project")
    _id = request.args.get("_id")
    mode = request.args.get("mode")
    vertebra = request.args.get("vertebra")
    database = mongo.db
    if mode == 'segmentation':
        database.quality_control.update_one({f"_id": _id, 'project': project},  {'$set': {f'quality_control.{vertebra}': 0, f'quality_control.SPINE': 1} })
    elif mode == 'labelling':
        database.quality_control.update_one({f"_id": _id,'project': project},  {'$set': {f'quality_control.SPINE': 0, f'quality_control.{vertebra}': 1} })
    elif mode == 'both':
        database.quality_control.update_one({f"_id": _id,'project': project},  {'$set': {f'quality_control.SPINE': 0, f'quality_control.{vertebra}': 0} })
    else:
        abort(400)

    res = make_response(jsonify({
        "message": "QA fail recorded"
    }), 200)

    return res


@bp.route('/api/sanity/get_summary', methods=['GET'])
def get_summary():
    #* Get recep of pass/fail/todo for current project
    project = request.args.get("project")
    vertebra = request.args.get("vertebra")

    database = mongo.db

    # Total documents 
    total = database.quality_control.count_documents({'project': project, f"overall_qc_state.{vertebra}": {"$exists": True} })
    # Pass labelling + segmentation
    num_pass = database.quality_control.count_documents({'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}, f"overall_qc_state.{vertebra}": 1 })

    num_fail = database.quality_control.count_documents({'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}, f"overall_qc_state.{vertebra}": 0 })
    num_todo = database.quality_control.count_documents({'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}, f"overall_qc_state.{vertebra}": 2 })

    # Fail either labelling 
    # failed_spine = database.quality_control.count_documents({'project': project, f"overall_qc_state.{vertebra}": {"$exists": True}, f"quality_control.{vertebra}.SPINE": 0})
    # # Fail segmentation
    # failed_segmentation = database.quality_control.count_documents({'project': project, f"quality_control.{vertebra}": {"$exists": True},
    #                                                                  "$and": [ {f"overall_qc_state.{vertebra}": 0}, {f"quality_control.{vertebra}.SPINE": 1} ]}) # If passed spine, but qc state failed must have failed segmentations
    # # Failed both 
    # failed_both = database.quality_control.count_documents({'project': project, f"quality_control.{vertebra}": {"$exists": True}, '$and': [ {"quality_control.SPINE": 0}, {f"quality_control.{vertebra}": 0}]})
    # Unreviewed
    # num_todo =database.quality_control.count_documents({'project': project, f"quality_control.{vertebra}": {"$exists": True},
    #                                                       '$or': [ {"quality_control.SPINE": 2}, {f"quality_control.{vertebra}": 2}]})

    #logger.info(f"Found {num_pass} successes and {failed_spine + failed_segmentation + failed_both} failures with {num_todo} still to review.")
    res =make_response(jsonify({
        "message": "Succesfully retrieved summary for current project",
        "pass": num_pass,
        "fail": num_fail,#{'spine': failed_spine, 'segmentation': failed_segmentation, 'both': failed_both},
        "todo": num_todo,
        "total": total
    }), 200)

    return res


@bp.route('/api/sanity/fail_qa_report', methods=['POST'])
def fail_qa_report():
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
    logger.info(f"Updated quality control collection with: {payload}")

    ##TODO Update qc control flag
    if payload[vertebra]["failMode"] == 'badSegmentation':
        database.quality_control.update_one({f"_id": _id, 'project': project},  {'$set': {f'quality_control.{vertebra}': 0, f'quality_control.SPINE': 1} })
    elif payload[vertebra]["failMode"] == 'wrongLevel':
        database.quality_control.update_one({f"_id": _id,'project': project},  {'$set': {f'quality_control.SPINE': 0, f'quality_control.{vertebra}': 1} })
    else:
        ## FailMode = Other or scan Issue fail both 
        ## Fail both
        database.quality_control.update_one({f"_id": _id,'project': project},  {'$set': {f'quality_control.SPINE': 0, f'quality_control.{vertebra}': 0} })

    res = make_response(jsonify({
        'message': 'Succesfully submitted report'
    }), 200)

    return res