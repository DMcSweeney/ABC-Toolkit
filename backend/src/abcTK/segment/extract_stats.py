"""
Main wrapper for extracting stats from a given segmentation.
Should import most methods from engine.py
"""
import os
import ast
import logging
from dataclasses import fields

from abcTK.segment.engine import segmentationEngine
from abcTK.inference.segment import get_loader_function
import abcTK.database.collections as cl


logger = logging.getLogger(__name__)


def extract_stats(req):
    """
    
    """
    logger.info(f"Request received: {req}")
    
    ## Check required params
    ## Assumes _id exists in project
    check_params(req, required_params=["_id", "mask_path", "project", "vertebra", "compartment"])
    from app import mongo
    database = mongo.db


    query = database.segmentation.find_one({"_id": req['_id'], "project": req['project']})
    if 'input_path' not in req:
        req['input_path'] = query['input_path']

    if 'output_dir' not in req:
        req['output_dir'] = query['output_dir']
    ## 

    req['loader_function'], loader_name = get_loader_function(req['input_path'])
    
    if type(req["vertebra"]) == list:
        logger.error("Make multiple requests to use multiple models.")
        raise ValueError("Vertebra should be a string representing a single level. Make multiple requests to use different models.")

    req = handle_request(req)
    # Set num_slices to None (i.e. to ignore this argument no matter what)
    # Figure this out based on the mask
    req['num_slices'] = None

    logger.info(f"Processing request: {req}")
    engine = segmentationEngine(**req)
    data, paths_to_sanity = engine.forward_extract_stats(**req)
    ## Update database
    update_database(req, data, paths_to_sanity)
    
    return


#* ===================== HELPERS =====================

def update_database(req, data, paths_to_sanity):
    from app import mongo

    database = mongo.db
    query = database.quality_control.find_one({'_id': req['_id'], 'project': req['project']},
                                                {"_id": 1, "quality_control": 1, "paths_to_sanity_images": 1})
    labelling = database.images.find_one({'_id': req['_id'], 'project': req['project']},
                                                {"_id": 1, "labelling_done":1})
    if labelling is not None:
        req['labelling_done'] = labelling['labelling_done']
    else:
        req['labelling_done'] = False

    qc = {req['vertebra']: 1, 'SPINE': 1} ## Set to pass since this mask should be manually edited/generated
    qc_report = {req['vertebra']: {}}
    if query is not None: #If an entry exists

    ## Update with existing values
        for k, v in query['paths_to_sanity_images'].items():
            if k in paths_to_sanity: # if this comprtment has been segmented, append or update                ...
                if type(v) == dict:
                    # Append. This should happen when adding a new vertebral level
                    if req['is_edit']:
                        tmp = {f'{x}-edited': y for x, y in paths_to_sanity[k].items()}
                    else:
                        tmp = {f'{x}-manual': y for x, y in paths_to_sanity[k].items()}
                    tmp.update({x: y for x, y in v.items()})
                    paths_to_sanity.update({k: tmp})
                # else:
                #     ## If only one item then leave it
                #     #paths_to_sanity[k] = 
            else:
                paths_to_sanity[k] = v
        
        for k, v in query['quality_control'].items():
            if k in qc: continue # Skip if level has just been segmented (i.e. set to 2)
            qc[k] = v
        
        if 'qc_report' in query:
            qc_report.update(query['qc_report'])

    
    ## Check if segmentation already done on this scan, if so update stats
    seg_query = database.segmentation.find_one({'_id': req['_id'], 'project': req['project']}, {"_id": 1, "all_parameters": 1, "statistics": 1})

    if req['is_edit']:
        key = f"{req['vertebra']}-edited"
    else:
        # If not edited, assume manually generated
        key = f"{req['vertebra']}-manual"
    
    all_parameters = {key: {k: str(v) for k, v in req.items()}}
    statistics = {key: data}
    if seg_query:
        if key in seg_query['statistics']:
            del seg_query['statistics'][key]
        if key in seg_query['all_parameters']:
            del seg_query['all_parameters'][key]

        # Keep all levels since this 
        all_parameters.update(seg_query['all_parameters'])
        statistics.update(seg_query['statistics'])


    #TODO Find a better way to fi
    img_query = database.images.find_one({'_id': req['_id'], 'project': req['project']})

    # Merge the two dicts but update values based on elements in req
    update = img_query | req
    
    field_names = [field.name for field in fields(cl.Images)]
    image_update = cl.Images(**{k: str(v) for k, v in update.items() if k in field_names})                                                                       

    seg_query = database.segmentation.find_one({'_id': req['_id'], 'project': req['project']})
    segmentation_update = cl.Segmentation(_id=req['_id'], project=req['project'], input_path=req['input_path'], 
                                            patient_id=seg_query['patient_id'], series_uuid=seg_query['series_uuid'], output_dir=req['output_dir'], statistics=statistics,
                                            all_parameters=all_parameters)

    qc_query = database.quality_control.find_one({'_id': req['_id'], 'project': req['project']})
    qc_update = cl.QualityControl(_id=req['_id'], project=req['project'], input_path=req['input_path'], patient_id=qc_query['patient_id'],
                                    series_uuid=qc_query['series_uuid'], paths_to_sanity_images=paths_to_sanity, quality_control=qc, qc_report=qc_report
                                    )

    database.images.update_one({"_id": req['_id']}, {"$set": image_update.__dict__}, upsert=True)
    logger.info(f"Set segmentation_done to True in collection: images")
    database.segmentation.update_one({"_id": req['_id']}, {'$set': segmentation_update.__dict__}, upsert=True)
    logger.info(f"Inserted {segmentation_update.__dict__} into collection: spine")
    database.quality_control.update_one({"_id": req['_id']}, {"$set": qc_update.__dict__}, upsert=True)
    logger.info(f"Inserted {qc_update.__dict__} into collection: quality_control")
    
def handle_request(req):
    from app import mongo 

    if 'is_edit' not in req:
        logger.info(f"Assuming the mask: {req['mask_path']} has been manually edited.")
        req['is_edit'] = True
    else:
        if not req['is_edit']:
            ## If is_edit is set to False
            logger.warn(f"Assuming the mask: {req['mask_path']} was manually generated.")
    
    if "dilate_mask" in req:
        if isinstance(req['dilate_mask'], str):
            if req['dilate_mask'].lower() in ['false', '0', 'no']:
                req['dilate_mask'] = False   
            elif req['dilate_mask'].lower() in ['true', '1', 'yes']:
                req['dilate_mask'] = True
            else:
                raise ValueError(f"Value not recognised: {req['dilate_mask']}. Use one of: False/True, 0/1, No/Yes")
             
    # WORLDMATCH OFFSET 
    # TODO HANDLE MR OFFSET - not sure of details...
    if 'worldmatch_correction' not in req:
        logger.info("Worldmatch correction (-1024 HU) will not be applied. Overwrite with 'worldmatch_correction' in request.")
        req['worldmatch_correction'] = False
    
    # BONE MASKS
    if 'generate_bone_mask' not in req:
        logger.info("Bone mask will be regenerated. This might slow things down. Overwrite with 'generate_bone_mask' in request (True-> regenerate; False-> skip).")
        req['generate_bone_mask'] = True
    elif type(req['generate_bone_mask']) == str:
        if req['generate_bone_mask'].lower() in ['false', '0', 'no']:
            req['generate_bone_mask'] = False   
        elif req['generate_bone_mask'].lower() in ['true', '1', 'yes']:
            req['generate_bone_mask'] = True
        else:
            # If can't be converted to bool assume path
            logger.info(f"Will not regenerate bone mask. Path to provided: {req['generate_bone_mask']}")

    # SLICE NUMBER
    if "slice_number" not in req:
        ## Check the spine collection for vertebra
        match = mongo.db.spine.find_one({"_id": req['_id']})
        if match is None or req["vertebra"] not in match["prediction"]:
            raise ValueError("Could not find a slice number for the requested vertebra.")
        req['slice_number'] = match["prediction"][req["vertebra"]][-1]
        logger.info(f"Found slice number {req['slice_number']} for {req['vertebra']}")
    else:
        ## If user provides a slice number, override the previous spine sanity image and generate a new image with only the level provided.  
        req['override_spine_sanity'] = True 

    if type(req['slice_number']) == str:
        req['slice_number'] = int(req['slice_number'])
    
    # MODALITY
    if "modality" not in req:
        ## If user doesn't provide modality, add default (CT)
        #TODO should this come from header? Might not handle CBCTs?
        logger.info("Assuming default modality: CT")
        req["modality"] = "CT"
    
    ## Muscle and fat thresholds
    if 'muscle_threshold' in req:
        req['muscle_threshold'] = ast.literal_eval(req['muscle_threshold'])
        req['muscle_threshold'] = [None if x == 'None' else x for x in req['muscle_threshold']]
        logger.info(f"Reading muscle_threshold from request: Low/High {req['muscle_threshold']}")

    if 'fat_threshold' in req:
        req['fat_threshold'] = ast.literal_eval(req['fat_threshold'])
        req['fat_threshold'] = [None if x == 'None' else x for x in req['fat_threshold']]
        logger.info(f"Reading fat_threshold from request: Low/High {req['fat_threshold']}")


    return req

def check_params(req, required_params):
    ## Check all args have been provided to inference call
    test = [x in req for x in required_params]
    if not all(test):
        logger.info(f"Some required parameters are missing. Did you provide the following? {required_params}")
        raise ValueError(f"Some required parameters are missing. Did you provide the following? {required_params}") ## Bad request
