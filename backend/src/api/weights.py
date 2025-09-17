"""
Endpoints for handling weights
"""

import logging
from flask import Blueprint, request, make_response, jsonify
import numpy as np

bp = Blueprint('api/weights', __name__)
logger = logging.getLogger(__name__)


@bp.route('/api/weights/post_weight', methods=["POST"])
def post_weight():
    patient_id = request.args.get('patient_id')
    weight = request.args.get('weight')
    date = request.args.get('date')

    from app import mongo
    database = mongo.db
    response = database.weights.find_one({'_id': patient_id})
    if response:
        measurements = response['measurements']
        logger.info(f'Found entry: {response}')
        measurements.update({date: weight})
    else:
        measurements = {date: weight}

    #TODO fetch and update previously entered measurements
    logger.info(f"Inserting {measurements} into collection: weights")
    
    database.weights.update_one({'_id': patient_id}, {"$set": {'patient_id': patient_id, 'measurements': measurements}}, upsert=True)

    res = make_response(jsonify({
        'message': f'Successfully inserted {weight} at {date} for {patient_id}'
    }), 200)

    return res


@bp.route('/api/weights/fetch_weights', methods=["GET"])
def fetch_weights():
    _id = request.args.get('_id')
    
    from app import mongo
    database = mongo.db
    response = database.weights.find_one({"_id": _id})
    if response: 
        data = response['measurements']
        if data:
            ## sort based on date -- Earliest to latest
            data = sorted(data.items(), reverse=False)
            
            ## calc weight change
            output_data = []
            baseline_date, baseline_weight = data[0]
            for date, weight in data:
                change = (float(weight)-float(baseline_weight))/float(baseline_weight)
                change *= 100
                change = np.round(change, 2)
                output_data.append((date, weight, change))
        else:
            output_data = []
    else:
        output_data = []

    res = make_response(jsonify({
        'message': f'Weight entries for {_id}',
        'data': output_data
        }), 200)

    return res


@bp.route('/api/weights/delete_weight', methods=["POST"])
def delete_weight():
    #TODO implement this! Delete an entry 
    ## Get patient ID and date
    _id = request.args.get("_id")
    date = request.args.get("date")

    from app import mongo
    database = mongo.db
    response = database.weights.find_one({'_id': _id})

    ## Drop date from measurements
    upd = response['measurements']
    del upd[date]

    logger.info(f'Removed {date} entry for {_id}')

    database.weights.update_one({'_id': _id}, {"$set": {'patient_id': _id, 'measurements': upd}})

    res = make_response(jsonify({
    'message': f'Deleted entry {date} for {_id}',
    }), 200)

    return res