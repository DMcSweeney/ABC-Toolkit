"""
Main wrapper for extracting stats from a given segmentation.
Should import most methods from engine.py
"""
import os
import ast
import shutil
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

    if req['is_edit']:
        _backup_original_mask_if_needed(req['output_dir'], req['vertebra'], req['compartment'])

    logger.info(f"Processing request: {req}")
    engine = segmentationEngine(**req)
    data, paths_to_sanity = engine.forward_extract_stats(**req)
    ## Update database
    update_database(req, data, paths_to_sanity)
    
    return


#* ===================== HELPERS =====================

def _backup_one_mask(mask_dir, tag):
    """Copy <tag>.nii.gz to <tag>_original.nii.gz if it exists and hasn't been backed up yet.
    Returns the backup path (whether just created or already existing), or None if there was
    nothing to back up. The backup itself is never overwritten."""
    canonical = os.path.join(mask_dir, f'{tag}.nii.gz')
    backup = os.path.join(mask_dir, f'{tag}_original.nii.gz')
    if not os.path.isfile(canonical):
        return None
    if not os.path.isfile(backup):
        shutil.copy2(canonical, backup)
        logger.info(f"Backed up original AI prediction before edit: {canonical} -> {backup}")
    return backup

def _backup_original_mask_if_needed(output_dir, vertebra, compartment):
    """Back up the mask a compartment edit is about to overwrite, the first time it's about
    to be overwritten, so the original AI prediction can be recovered later. No-op if
    already backed up or nothing exists yet. 'total_muscle' is a real persisted file
    (engine.py writes masks/<vertebra>/total_muscle.nii.gz in both forward() and
    forward_extract_stats(), before IMAT is carved out of it) so it needs no special
    handling here - it's backed up exactly like any other compartment."""
    mask_dir = os.path.join(output_dir, 'masks', vertebra)
    _backup_one_mask(mask_dir, compartment)

def _aggregate_qc_state(qc):
    """Collapse quality_control into a scalar-per-vertebra overall_qc_state. A vertebra's
    quality_control value can either already be scalar (set directly by this edit-recompute
    path) or a nested per-compartment dict (set by the full-inference path in
    abcTK/inference/segment.py, and carried forward here for any untouched vertebra) -
    overall_qc_state must always be scalar, so mirror that path's own aggregation
    (2 if any compartment needs doing, else 0 if any failed, else 1) for the dict case."""
    overall_qc_state = {}
    for vertebra, val in qc.items():
        if not isinstance(val, dict):
            overall_qc_state[vertebra] = val
        elif any(v == 2 for v in val.values()):
            overall_qc_state[vertebra] = 2
        elif any(v == 0 for v in val.values()):
            overall_qc_state[vertebra] = 0
        else:
            overall_qc_state[vertebra] = 1
    return overall_qc_state

def update_database(req, data, paths_to_sanity):
    from app import mongo

    database = mongo.db
    vertebra = req['vertebra']
    query = database.quality_control.find_one({'_id': req['_id'], 'project': req['project']},
                                                {"_id": 1, "quality_control": 1, "paths_to_sanity_images": 1,
                                                 "original_paths_to_sanity_images": 1})
    labelling = database.images.find_one({'_id': req['_id'], 'project': req['project']},
                                                {"_id": 1, "labelling_done":1})
    if labelling is not None:
        req['labelling_done'] = labelling['labelling_done']
    else:
        req['labelling_done'] = False

    qc = {vertebra: 1, 'SPINE': 1} ## Set to pass since this mask should be manually edited/generated
    qc_report = {vertebra: {}}
    original_paths = {}
    if query is not None: #If an entry exists
        original_paths = dict(query.get('original_paths_to_sanity_images', {}))

        ## paths_to_sanity holds this run's fresh {vertebra: path} per compartment (incl.
        ## 'ALL') - always overwrite the bare vertebra key in place from now on (no more
        ## -edited/-manual suffixed sibling keys), stashing whatever was there before the
        ## first time each (compartment, vertebra) pair gets overwritten.
        for k, v in query['paths_to_sanity_images'].items():
            if k not in paths_to_sanity:
                paths_to_sanity[k] = v # untouched compartment - carry forward as-is
                continue
            prev = v.get(vertebra) if isinstance(v, dict) else v
            if prev is not None:
                original_paths.setdefault(k, {})
                original_paths[k].setdefault(vertebra, prev)
            if isinstance(v, dict):
                merged = dict(v)
                merged.update(paths_to_sanity[k]) # this run's fresh path wins
                paths_to_sanity[k] = merged

        for k, v in query['quality_control'].items():
            if k in qc: continue # Skip if level has just been segmented (i.e. set to 2)
            qc[k] = v

        if 'qc_report' in query:
            qc_report.update(query['qc_report'])


    ## Check if segmentation already done on this scan, if so update stats
    seg_query = database.segmentation.find_one({'_id': req['_id'], 'project': req['project']}, {"_id": 1, "all_parameters": 1, "statistics": 1})

    ## statistics[vertebra] holds every compartment as a sibling key (current value, edited
    ## or not) plus a reserved '_original' sibling key nesting a per-compartment snapshot of
    ## whatever was there the first time that compartment was ever edited. `data` holds every
    ## compartment key actually recomputed this call - e.g. a 'total_muscle' edit recomputes
    ## both 'skeletal_muscle' and 'IMAT' in one go, not just req['compartment'] verbatim.
    vert_stats = dict(seg_query['statistics'].get(vertebra, {})) if seg_query else {}
    orig_stats = dict(vert_stats.get('_original', {}))
    for comp in data.keys():
        if comp not in orig_stats and comp in vert_stats:
            orig_stats[comp] = vert_stats[comp] # stash pre-edit stats, once, per compartment
    vert_stats.update(data)
    if orig_stats:
        vert_stats['_original'] = orig_stats

    ## all_parameters[vertebra] stays a flat "whatever request produced the current state"
    ## dict (matching abcTK/inference/segment.py's own update_database, which writes the same
    ## shape for the full-inference path) with one reserved '_original' key holding the flat
    ## params dict from before the very first edit of this vertebra.
    vert_params = dict(seg_query['all_parameters'].get(vertebra, {})) if seg_query else {}
    orig_params = vert_params.get('_original')
    if orig_params is None and vert_params:
        orig_params = {k: v for k, v in vert_params.items() if k != '_original'}
    new_params = {k: str(v) for k, v in req.items()}
    if orig_params is not None:
        new_params['_original'] = orig_params

    statistics = dict(seg_query['statistics']) if seg_query else {}
    statistics[vertebra] = vert_stats
    all_parameters = dict(seg_query['all_parameters']) if seg_query else {}
    all_parameters[vertebra] = new_params

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
                                    series_uuid=qc_query['series_uuid'], paths_to_sanity_images=paths_to_sanity, quality_control=qc, qc_report=qc_report,
                                    overall_qc_state=_aggregate_qc_state(qc), original_paths_to_sanity_images=original_paths
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
