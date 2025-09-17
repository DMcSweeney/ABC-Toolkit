"""
Script containing post-processing endpoints
"""
import os
import logging
from flask import Blueprint, make_response, jsonify, request, current_app, send_file
from app import mongo
import SimpleITK as sitk
import numpy as np
import json
import polars as pl
import shutil
import datetime

from rt_utils import RTStructBuilder


bp = Blueprint('api/post_process', __name__)
logger = logging.getLogger(__name__)

@bp.route('/api/post_process/get_rt_struct', methods=["POST"])
def getRTStruct():
    req = request.get_json()
    _id = req["_id"]
    project = req["project"]
    for_editing = True if req['for_editing'] == 'True' else False

    database = mongo.db 
    response = database.segmentation.find_one({f"_id": _id, "project": project})
    path_to_preds = os.path.join(response['output_dir'], 'masks')

    ## Go through output dir and read all masks into one RT-Struct
    Masks = {filename.rstrip('.nii.gz'): sitk.ReadImage(os.path.join(path_to_preds, filename)) \
             for filename in os.listdir(path_to_preds) if filename.endswith('.nii.gz')}

    ### Account for different mount points
    if 'arc001' in response['input_path']: # If reading from xnat archive
        input_path = response['input_path'].replace('/data/inputs/', '/data/inputs/xnat/1.8/archive/') 
    else:
        input_path = response['input_path']
    logger.info(f"Reading DICOM from {input_path}")


    # Point RTSTruct Builder to input dicom
    rtstruct = RTStructBuilder.create_new(dicom_series_path=input_path)
    for name, Mask in Masks.items():
        mask = sitk.GetArrayFromImage(Mask).astype(bool) ## Need to re-order axes to match 
        mask = np.moveaxis(np.transpose(mask), 0, 1)
        logger.info(f"Adding {name} to RT-Struct. Shape: {mask.shape}")
        rtstruct.add_roi(mask=mask, name=name)

    ## Save RT struct and reply
    if for_editing:
        output_path = os.path.join('/data/outputs', project, 'masks_to_edit', response['patient_id'], _id, 'rt-struct.dcm')
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
 
        shutil.copytree(input_path, os.path.join(output_dir, 'SCAN'))

    else:
        output_path = os.path.join(path_to_preds, 'rt-struct.dcm')
    
    rtstruct.save(output_path)

    res = make_response(jsonify({
        "message": "RT-Struct successfully generated.",
        "output_path": output_path
    }), 200)

    return res
    
@bp.route('/api/post_process/get_stats_for_series', methods=["POST"])
def get_stats():
    req = request.get_json()
    _id = req['_id']
    project = req['project']

    if 'format' in req:
        ###
        ...
    else:
        req['format'] = 'voxels'

    vertebra = 'L3' ##TODO This should be a variable
    
    database = mongo.db
    response = database.segmentation.find_one({"_id": _id, "project": project})
    data = {}
    for type_, dict_ in response["statistics"].items():
        if req['format'] == 'metric':
            logger.info("Converting areas to mm2")

            spacing = database.images.find_one({"_id": _id, "project": project}, {'X_spacing': 1, 'Y_spacing': 1, 'slice_thickness': 1})
            
        areas = [x['area (voxels)'] for x in dict_.values()]
        densities = [x['density (HU)'] for x in dict_.values()]
        data[type_] = {'mean-area': np.mean(areas), 'stdev-area': np.std(areas),
                        'mean-density': np.mean(densities), 'stdev-density': np.std(densities),
                        **dict_}

    res = make_response(jsonify({
        "message": "Stats returned successfully",
        "data": data
    }), 200)
    return res

@bp.route('/api/post_process/get_stats_for_project_v2', methods=['GET'])
def getStatsForProjectv2():
    project = request.args.get('project')
    download = True if request.args.get("download") == 'True' else False


    database = mongo.db
    response = database.segmentation.find({"project": project})

    df = pl.DataFrame()
    for doc in response:
        spacing = database.images.find_one({"project": project, "_id": doc["_id"]}, {'X_spacing': 1, 'Y_spacing': 1, 'slice_thickness': 1})
        qc = database.quality_control.find_one({"project": project, "_id": doc["_id"]}, {'quality_control': 1}) ## Get the per-vertebra + per-compartment QA results

        if not qc:
            logger.warning(f"{doc['_id']} did not pass quality control, skipping")
            continue
        
        verts = list(qc['quality_control'].keys())

        ## Catch manual edits
        if any(['edited' in x for x in doc['statistics'].keys()]):
            for vertebra_edited, data in doc["statistics"].items(): # Key should be format: VERTEBRA-edited or just VERTEBRA
                if 'edited' in vertebra_edited:
                    vertebra = vertebra_edited.rstrip('-edited')
                else:
                    vertebra = vertebra_edited
                
                for compartment, dict_ in data.items():
                    
                    for slice_, value in dict_.items():
                        slice_num = int(slice_.lstrip('Slice'))

                        row = {"patient_id": doc["patient_id"], "series_uuid": doc["series_uuid"], "acquisition_date": doc["all_parameters"][vertebra_edited]["acquisition_date"] if "acquisition_date" in doc["all_parameters"][vertebra_edited] else "nan",
                            "vertebra": vertebra, "compartment": compartment, "area": value['area (voxels)'], "density": value['density (HU)'], "is_edit": True if 'edited' in vertebra_edited else False,
                            "slice_number": slice_num, "X_spacing": float(spacing['X_spacing']), "Y_spacing": float(spacing['Y_spacing']), "slice_thickness": float(spacing['slice_thickness']),
                                "spine_qc": float(qc["quality_control"][vertebra]["SPINE"]) if "SPINE" in qc['quality_control'][vertebra] else float("nan"), f"{vertebra}_qc": float(qc["quality_control"][vertebra][compartment]) if vertebra in qc["quality_control"] else float("nan")
                                }
                        tmp = pl.DataFrame(row)
                        df = pl.concat([df, tmp], how="diagonal")


        for vertebra, data in doc["statistics"].items():
            if vertebra not in verts: ## This is to catch entries that were initially the old format {compartment: area/density} and were appended with the new format {level: {compartment: area/density}}
                print(f'Skipping {vertebra}', flush=True)
                continue
            for compartment, dict_ in data.items():\
                
                for slice_, value in dict_.items():
                    slice_num = int(slice_.lstrip('Slice'))

                    row = {"patient_id": doc["patient_id"], "series_uuid": doc["series_uuid"], "acquisition_date": doc["all_parameters"][vertebra]["acquisition_date"],
                        "vertebra": vertebra, "compartment": compartment, "area": value['area (voxels)'], "density": value['density (HU)'], "is_edit": False,
                        "slice_number": slice_num, "X_spacing": float(spacing['X_spacing']), "Y_spacing": float(spacing['Y_spacing']), "slice_thickness": float(spacing['slice_thickness']),
                            "spine_qc": float(qc["quality_control"][vertebra]["SPINE"]) if "SPINE" in qc['quality_control'][vertebra] else float("nan"),
                            f"{vertebra}_qc": float(qc["quality_control"][vertebra][compartment]) if vertebra in qc["quality_control"] else float("nan")
                            }
                    tmp = pl.DataFrame(row)
                    df = pl.concat([df, tmp], how="diagonal")

    if df.is_empty():
        res = make_response(jsonify({
            "message": "No examples passed quality control.",
        }), 400)
        return res

    output_filename = os.path.join(current_app.config['OUTPUT_DIR'], project, 'statistics.csv') 
    df.write_csv(output_filename)

    if download:#
        logger.info(f"Sending {output_filename} to user")
        filename = f"{project}_statistics.csv"
        return send_file(output_filename, download_name=filename, as_attachment=True, mimetype="application/octet-stream")
    
    res = make_response(jsonify({
        "message": "Stats returned successfully",
        "output_file": output_filename
    }), 200)
    return res

@bp.route('/api/post_process/get_stats_for_project', methods=["GET"])
def get_stats_for_project():
    project = request.args.get('project')
    download = True if request.args.get("download") == 'True' else False


    database = mongo.db
    response = database.segmentation.find({"project": project})

    df = pl.DataFrame()
    for doc in response:
        spacing = database.images.find_one({"project": project, "_id": doc["_id"]}, {'X_spacing': 1, 'Y_spacing': 1, 'slice_thickness': 1})
        qc = database.quality_control.find_one({"project": project, "_id": doc["_id"]}, {'quality_control': 1})
        if not qc:
            logger.warn(f"{doc['_id']} did not pass quality control, skipping")
            continue
        verts = {f"{k}": v for k, v in qc['quality_control'].items() if k != "SPINE"}
        
        #TODO THIS CAN BE WRITTEN IN A MUCH BETTER WAY....
        ## Check if entry has been edited
        if any(['edited' in x for x in doc['statistics'].keys()]):
            for vertebra_edited, data in doc["statistics"].items(): # Key should be format: VERTEBRA-edited or just VERTEBRA
                if 'edited' in vertebra_edited:
                    vertebra = vertebra_edited.rstrip('-edited')
                else:
                    vertebra = vertebra_edited
                
                if vertebra not in verts: ## This is to catch entries that were initially the old format {compartment: area/density} and were appended with the new format {level: {compartment: area/density}}
                    print(f'Skipping {vertebra}', flush=True)
                    continue
                for type_, dict_ in data.items():
                    
                    for slice_, value in dict_.items():
                        slice_num = int(slice_.lstrip('Slice'))

                        row = {"patient_id": doc["patient_id"], "series_uuid": doc["series_uuid"], "acquisition_date": doc["all_parameters"][vertebra_edited]["acquisition_date"] if "acquisition_date" in doc["all_parameters"][vertebra_edited] else "nan",
                            "vertebra": vertebra, "compartment": type_, "area": value['area (voxels)'], "density": value['density (HU)'], "is_edit": True if 'edited' in vertebra_edited else False,
                            "slice_number": slice_num, "X_spacing": float(spacing['X_spacing']), "Y_spacing": float(spacing['Y_spacing']), "slice_thickness": float(spacing['slice_thickness']),
                                "spine_qc": float(qc["quality_control"]["SPINE"]) if "SPINE" in qc['quality_control'] else float("nan"), f"{vertebra}_qc": float(qc["quality_control"][vertebra]) if vertebra in qc["quality_control"] else float("nan")
                                }
                        tmp = pl.DataFrame(row)
                        df = pl.concat([df, tmp], how="diagonal")


        if any([x in verts for x in doc["statistics"].keys()]): # This is the new way of writing to the database (i.e. splitting everything on vertebral level)
            
            for vertebra, data in doc["statistics"].items():
                if vertebra not in verts: ## This is to catch entries that were initially the old format {compartment: area/density} and were appended with the new format {level: {compartment: area/density}}
                    print(f'Skipping {vertebra}', flush=True)
                    continue
                for type_, dict_ in data.items():\
                    
                    for slice_, value in dict_.items():
                        slice_num = int(slice_.lstrip('Slice'))

                        row = {"patient_id": doc["patient_id"], "series_uuid": doc["series_uuid"], "acquisition_date": doc["all_parameters"][vertebra]["acquisition_date"],
                            "vertebra": vertebra, "compartment": type_, "area": value['area (voxels)'], "density": value['density (HU)'], "is_edit": False,
                            "slice_number": slice_num, "X_spacing": float(spacing['X_spacing']), "Y_spacing": float(spacing['Y_spacing']), "slice_thickness": float(spacing['slice_thickness']),
                                "spine_qc": float(qc["quality_control"]["SPINE"]) if "SPINE" in qc['quality_control'] else float("nan"), f"{vertebra}_qc": float(qc["quality_control"][vertebra]) if vertebra in qc["quality_control"] else float("nan")
                                }
                        tmp = pl.DataFrame(row)
                        df = pl.concat([df, tmp], how="diagonal")
        else: # This is the old way but keeping here to catch exceptions
            for type_, dict_ in doc["statistics"].items():
                if type_ not in ['IMAT', 'skeletal_muscle', 'visceral_fat', 'subcutaneous_fat']:
                    print(f'Skipping {type_}', flush=True)
                    continue
                for slice_, value in dict_.items():
                    slice_num = int(slice_.lstrip('Slice'))
                    vertebra = doc["all_parameters"]["vertebra"]
                    row = {"patient_id": doc["patient_id"], "series_uuid": doc["series_uuid"], "acquisition_date": doc["all_parameters"]["acquisition_date"] if "acquisition_date" in doc["all_parameters"] else "None",
                        "vertebra": vertebra, "compartment": type_, "area": value['area (voxels)'], "density": value['density (HU)'], "is_edit": False,
                        "slice_number": slice_num, "X_spacing": float(spacing['X_spacing']), "Y_spacing": float(spacing['Y_spacing']), "slice_thickness": float(spacing['slice_thickness']),
                            "spine_qc": float(qc["quality_control"]["SPINE"]) if "SPINE" in qc['quality_control'] else float("nan"), f"{vertebra}_qc": float(qc["quality_control"][vertebra]) if vertebra in qc["quality_control"] else float("nan")
                            }
                    tmp = pl.DataFrame(row)
                    df = pl.concat([df, tmp], how="diagonal")

    if df.is_empty():
        res = make_response(jsonify({
            "message": "No examples passed quality control.",
        }), 400)
        return res

    output_filename = os.path.join(current_app.config['OUTPUT_DIR'], project, 'statistics.csv') 
    df.write_csv(output_filename)

    if download:#
        logger.info(f"Sending {output_filename} to user")
        filename = f"{project}_statistics.csv"
        return send_file(output_filename, download_name=filename, as_attachment=True, mimetype="application/octet-stream")
    
    res = make_response(jsonify({
        "message": "Stats returned successfully",
        "output_file": output_filename
    }), 200)
    return res

@bp.route('/api/post_process/export_segmentations', methods=["POST"])
def export_segmentations():
    req = request.get_json()
    _id = req['_id']
    project = req['project']
    compartment = req['compartment']
    output_dir_name = req['output_dir_name']

    compartment_to_filename = {
        'total_muscle': ['skeletal_muscle.nii.gz', 'MUSCLE.nii.gz', 'IMAT.nii.gz'],
        'skeletal_muscle': ['MUSCLE.nii.gz', 'skeletal_muscle.nii.gz'], # I changed naming convention half-way through for some reason...
        'visceral_fat': ['VISCERAL_FAT.nii.gz', 'visceral_fat.nii.gz'],
        'subcutaneous_fat': ['SUBCUT_FAT.nii.gz', 'subcutaneous_fat.nii.gz'],
        'IMAT': 'IMAT.nii.gz',
        'bone': 'BONE.nii.gz',
    }
    assert compartment in compartment_to_filename

    # Query database and get path to mask
    from app import mongo
    database = mongo.db
    
    res = database.segmentation.find_one({"_id": _id, "project": project})

    ## Find the mask to move
    if compartment == 'total_muscle':
        # If total muscle, read MUSCLE and IMAT masks, and combine
        holder = []
        for file in compartment_to_filename[compartment]:
            logger.info(f"Adding {file} to mask.")
            try:
                Mask = sitk.ReadImage(os.path.join(res['output_dir'], 'masks', file)) 
            except RuntimeError:
                logger.warn(f"Could not find mask {file} in {os.path.join(res['output_dir'], 'masks')}")
                continue
            logger.info(f"Read mask with size {Mask.GetSize()}")
            mask = sitk.GetArrayFromImage(Mask).astype(int)
            holder.append(mask[None]) # Add extra dimension to stack along
        total_muscle_mask = np.max(np.vstack(holder), axis=0)
        Total_muscle_mask = sitk.GetImageFromArray(total_muscle_mask)
        Total_muscle_mask.CopyInformation(Mask)
        path_to_mask = os.path.join(res['output_dir'], 'masks', 'TOTAL_MUSCLE.nii.gz')

        logger.info(f"Writing total muscle mask to {path_to_mask}")
        sitk.WriteImage(Total_muscle_mask, path_to_mask)
    
    else:
        for file in compartment_to_filename[compartment]:
            try:
                path_to_mask = os.path.join(res['output_dir'], 'masks', compartment_to_filename[compartment])
            except RuntimeError:
                logger.warn(f"Could not find mask {file} in {os.path.join(res['output_dir'], 'masks')}")
                continue
        print(path_to_mask, flush=True)
    
    # Get path to scan
    #TODO THIS IS A TEMPORARY FIX AND NEEDS TO GO ASAP
    ### Account for different mount points
    if 'arc001' in res['input_path']: # If reading from xnat archive
        input_path = res['input_path'].replace('/data/inputs/', '/data/inputs/xnat/1.8/archive/')
    elif '/inputs/AJ/' in res['input_path'] \
        or '/inputs/AG/' in res['input_path'] \
        or '/inputs/ACE/' in res['input_path']:
        input_path = res['input_path'].replace('/data/inputs/', '/data/inputs/All Scans/baselineCTs/')
    elif 'AJ_baseline_CT' in res['input_path']:
        input_path = res['input_path'].replace('/data/inputs/', '/data/inputs/All Scans/')
        logger.info(f"Converted AJ_Baseline path: {input_path}. Originally {res['input_path']}")
    elif '/BaselineAnalysis/re_run_salvage_level_issues/' in res['input_path']:
        input_path = res['input_path'].replace('re_run_salvage_level_issues', 'salvage_level_issues')
        logger.info(f"Converted salvage issue path: {input_path}. Originally {res['input_path']}")
    else:
        logger.info("No match detected")
        input_path = res['input_path']
    logger.info(f"Reading DICOM from {input_path}")

    # Copy to output directory
    output_dir = os.path.join('/data/outputs', project,  output_dir_name, res['patient_id'].strip(), _id)
    os.makedirs(output_dir, exist_ok=True)
    shutil.copy(path_to_mask, output_dir)
    shutil.copytree(input_path, os.path.join(output_dir, 'SCAN'))
    
    res = make_response(jsonify({
        "message": "Exported segmentation for editing",
        "output_directory": output_dir
    }), 200)
    return res


@bp.route('/api/post_process/get_stats_for_patient', methods=['GET'])
def get_stats_for_patient():
    ### Get all measurements for a patient
    # Muscle, fat
    project = request.args.get("project")
    patient_id = request.args.get("patient_id")
    vertebra = request.args.get("vertebra")
    compartment = request.args.get("compartment")
    
    logger.info(f'Fetching body comp stats for {patient_id} in {project}')
    from app import mongo
    database = mongo.db
    cursors = database.segmentation.find({'project': project, 'patient_id': patient_id})

    if cursors:
        data = []
        for cursor in cursors:
            ## For each entry, extract series_uuid and match to date in images
            image_query = database.images.find_one({'_id': cursor['_id']})
            acq_date = image_query['acquisition_date']
            acq_date = datetime.datetime.strptime(image_query['acquisition_date'], "%d-%m-%Y").strftime("%Y-%m-%d") 
            ## Get pixel data to convert measurements to mm
            pix_area = float(image_query['X_spacing']) * float(image_query['Y_spacing']) 

            ## Get stats for every compartment
            stats = cursor['statistics']
            areas = {}
            densities = {}
            for level, level_stats in stats.items():
                if level != vertebra: continue
                areas[level] = {}
                densities[level] = {}
                for compartment, slice_dict in level_stats.items():
                    if compartment != compartment: continue
                    ## Get mean across every slice? 
                    #TODO make this variable ? Median? STDev

                    mean_area = np.mean([v['area (voxels)'] for k, v in slice_dict.items()])
                    mean_area *= pix_area ## Convert to mm2
                    mean_area /= 100 ## Convert to cm2
                    mean_density = np.mean([v['density (HU)'] for k, v in slice_dict.items()])

                    areas[level].update({compartment: mean_area})
                    densities[level].update({compartment: mean_density})
            data.append((acq_date, areas, densities))
        
        data = sorted(data, key=lambda x: x[0] )

        ##TODO Calc change relative to first 
        baseline_date, baseline_area, baseline_density = data[0]

        changes = [(baseline_date, baseline_area[vertebra][compartment], baseline_density[vertebra][compartment])]
        for elem in data:
            date = elem[0]
            #if date == baseline_date: continue
            area = elem[1][vertebra][compartment]
            density = elem[2][vertebra][compartment]
            logger.info(f"{elem[0]} - {area} - {density}")
            area_change = (area-baseline_area[vertebra][compartment])/baseline_area[vertebra][compartment]
            area_change *= 100

            density_change = (density-baseline_density[vertebra][compartment])/baseline_density[vertebra][compartment]
            density_change *= 100

            changes.append((date, area_change, density_change))


        res = make_response(jsonify({
            "message": "Found stats",
            "data": changes
        }), 200)
        return res
    else:
        res = make_response(jsonify({
            "message": f"No stats found for {patient_id} in {project}",
        }), 500)
        return res
