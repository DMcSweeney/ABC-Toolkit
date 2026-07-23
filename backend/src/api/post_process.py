"""
Script containing post-processing endpoints
"""
import os
import io
import logging
from flask import Blueprint, make_response, jsonify, request, current_app, send_file
from app import mongo
import SimpleITK as sitk
import numpy as np
import json
import polars as pl
import shutil
import datetime

import matplotlib
matplotlib.use('Agg')  # headless server-side rendering, no display available in the container
import matplotlib.pyplot as plt

from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle

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


def _fetch_patient_trend_data(database, project, patient_id, vertebra, compartment, modality=None):
    """
    Shared logic for building a patient's longitudinal trend series for one
    (vertebra, compartment[, modality]) combination. Used by both the
    get_stats_for_patient HTTP endpoint and the PDF report generator (generate_report),
    so both apply the exact same QC-exclusion/baseline rules rather than risking two
    diverging implementations.

    Failed-QC segmentations (overall_qc_state[vertebra] == 0) are excluded *before*
    sorting/choosing the % change baseline -- a failed scan used as the baseline would
    corrupt every later point's relative value, even once the failed point itself is
    hidden from display.
    """
    cursors = database.segmentation.find({'project': project, 'patient_id': patient_id})

    data = []
    for cursor in cursors:
        level_stats = cursor.get('statistics', {}).get(vertebra)
        if level_stats is None or compartment not in level_stats:
            continue

        image_query = database.images.find_one({'_id': cursor['_id'], 'project': project})
        if image_query is None:
            continue
        if modality and image_query.get('modality') != modality:
            continue

        qc_query = database.quality_control.find_one({'_id': cursor['_id'], 'project': project}, {'overall_qc_state': 1})
        qc_status = qc_query['overall_qc_state'].get(vertebra) if qc_query and 'overall_qc_state' in qc_query else 2
        if qc_status == 0:
            # Failed QC -- exclude entirely, don't let it become the baseline.
            continue

        try:
            acq_date = datetime.datetime.strptime(image_query['acquisition_date'], "%d-%m-%Y").strftime("%Y-%m-%d")
        except (ValueError, TypeError, KeyError):
            continue

        pix_area = float(image_query['X_spacing']) * float(image_query['Y_spacing'])
        slice_dict = level_stats[compartment]
        mean_area = np.mean([v['area (voxels)'] for v in slice_dict.values()])
        mean_area = mean_area * pix_area / 100  # voxels -> mm2 -> cm2
        mean_density = np.mean([v['density (HU)'] for v in slice_dict.values()])

        data.append({
            'date': acq_date,
            'series_uuid': cursor.get('series_uuid', cursor['_id']),
            'area': float(mean_area),
            'density': float(mean_density),
            'qc_status': qc_status,
        })

    if not data:
        return []

    data = sorted(data, key=lambda x: x['date'])
    baseline = data[0]
    for point in data:
        point['area_pct_change'] = ((point['area'] - baseline['area']) / baseline['area']) * 100 if baseline['area'] else 0.0
        point['density_pct_change'] = ((point['density'] - baseline['density']) / baseline['density']) * 100 if baseline['density'] else 0.0

    return data


@bp.route('/api/post_process/get_stats_for_patient', methods=['GET'])
def get_stats_for_patient():
    ### Get all measurements for a patient at one (vertebra, compartment[, modality])
    project = request.args.get("project")
    patient_id = request.args.get("patient_id")
    vertebra = request.args.get("vertebra")
    compartment = request.args.get("compartment")
    modality = request.args.get("modality")  # optional

    logger.info(f'Fetching body comp stats for {patient_id} in {project}')
    database = mongo.db

    data = _fetch_patient_trend_data(database, project, patient_id, vertebra, compartment, modality)

    if not data:
        res = make_response(jsonify({
            "message": f"No stats found for {patient_id} in {project}",
        }), 500)
        return res

    res = make_response(jsonify({
        "message": "Found stats",
        "data": data
    }), 200)
    return res


@bp.route('/api/post_process/get_population_stats', methods=['GET'])
def get_population_stats():
    """
    Project-wide distribution of one (vertebra, compartment[, modality]) metric, one value
    per matching series across every patient in the project -- used to plot where a specific
    patient's own measurements sit relative to the rest of the project. Excludes failed-QC
    segmentations, the same rule as get_stats_for_patient/_fetch_patient_trend_data, so the
    population isn't skewed by bad segmentations either.
    """
    project = request.args.get("project")
    vertebra = request.args.get("vertebra")
    compartment = request.args.get("compartment")
    modality = request.args.get("modality")

    database = mongo.db
    docs = database.segmentation.find({"project": project})

    data = []
    for doc in docs:
        level_stats = doc.get('statistics', {}).get(vertebra)
        if level_stats is None or compartment not in level_stats:
            continue

        image_query = database.images.find_one({'_id': doc['_id'], 'project': project})
        if image_query is None:
            continue
        if modality and image_query.get('modality') != modality:
            continue

        qc_query = database.quality_control.find_one({'_id': doc['_id'], 'project': project}, {'overall_qc_state': 1})
        qc_status = qc_query['overall_qc_state'].get(vertebra) if qc_query and 'overall_qc_state' in qc_query else 2
        if qc_status == 0:
            continue

        try:
            acq_date = datetime.datetime.strptime(image_query['acquisition_date'], "%d-%m-%Y").strftime("%Y-%m-%d")
        except (ValueError, TypeError, KeyError):
            acq_date = None

        pix_area = float(image_query['X_spacing']) * float(image_query['Y_spacing'])
        slice_dict = level_stats[compartment]
        mean_area = np.mean([v['area (voxels)'] for v in slice_dict.values()]) * pix_area / 100
        mean_density = np.mean([v['density (HU)'] for v in slice_dict.values()])

        data.append({
            'patient_id': doc['patient_id'],
            'date': acq_date,
            'area': float(mean_area),
            'density': float(mean_density),
        })

    res = make_response(jsonify({
        "message": f"Found {len(data)} population data points",
        "data": data
    }), 200)
    return res


@bp.route('/api/post_process/generate_report', methods=['POST'])
def generate_report():
    """
    Build a clinical PDF report for a patient: a longitudinal trend chart covering the
    requested (vertebra, compartment[, modality]) combos, a weight-history table, and a
    grid of exemplar QA images sampled roughly weekly. Reuses _fetch_patient_trend_data
    (the same function get_stats_for_patient calls) so the report's QC-exclusion/baseline
    rules can never drift from what's shown on screen.
    """
    req = request.get_json()
    project = req['project']
    patient_id = req['patient_id']
    combos = req['combos']  # [{vertebra, compartment, modality}, ...]

    database = mongo.db

    # 1. Trend data per combo.
    trend_series = {}
    for combo in combos:
        label = f"{combo['vertebra']} · {combo['compartment']}"
        series = _fetch_patient_trend_data(database, project, patient_id, combo['vertebra'], combo['compartment'], combo.get('modality'))
        if series:
            trend_series[label] = series

    # 2. Render the trend chart with matplotlib -- always light/white, independent of the
    # web app's current theme, since printed reports default to light for readability.
    chart_buffer = None
    if trend_series:
        fig, ax = plt.subplots(figsize=(7, 4))
        for label, series in trend_series.items():
            dates = [p['date'] for p in series]
            values = [p['area_pct_change'] for p in series]
            ax.plot(dates, values, marker='o', label=label)
        ax.set_xlabel('Date')
        ax.set_ylabel('Area % change from baseline')
        ax.set_title(f'Body composition trend — {patient_id}')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        chart_buffer = io.BytesIO()
        fig.savefig(chart_buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        chart_buffer.seek(0)

    # 3. Weight history.
    weight_doc = database.weights.find_one({'_id': patient_id})
    weight_rows = sorted(weight_doc['measurements'].items()) if weight_doc and weight_doc.get('measurements') else []

    # 4. Exemplar QA images, ~1/week, for the first requested combo's vertebra (v1 scope --
    # not every selected vertebra, documented as a deliberate simplification).
    exemplar_images = []
    if combos:
        primary_vertebra = combos[0]['vertebra']
        qc_docs = database.quality_control.find({'project': project, 'patient_id': patient_id})
        scans = []
        for qc in qc_docs:
            img = database.images.find_one({'_id': qc['_id'], 'project': project})
            if img is None:
                continue
            try:
                acq_date = datetime.datetime.strptime(img['acquisition_date'], "%d-%m-%Y")
            except (ValueError, TypeError, KeyError):
                continue

            all_paths = qc.get('paths_to_sanity_images', {}).get('ALL')
            if all_paths is None:
                continue
            # 'ALL' is either a plain path string, or a {vertebra: path} dict -- same
            # defensive check used at the existing read sites (api/sanity.py, api/patientQA.py).
            path = all_paths.get(primary_vertebra) if isinstance(all_paths, dict) else all_paths
            if path and os.path.exists(path):
                scans.append((acq_date, path))

        scans.sort(key=lambda x: x[0])
        last_bucket_date = None
        for acq_date, path in scans:
            if last_bucket_date is None or (acq_date - last_bucket_date).days >= 7:
                exemplar_images.append((acq_date.strftime('%Y-%m-%d'), path))
                last_bucket_date = acq_date

    # 5. Compose the PDF with ReportLab.
    output_dir = os.path.join(current_app.config['OUTPUT_DIR'], project, patient_id, 'reports')
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    output_path = os.path.join(output_dir, f'{patient_id}_report_{timestamp}.pdf')

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Body Composition Report", styles['Title']),
        Paragraph(f"Patient: {patient_id} &nbsp;&nbsp;&nbsp; Project: {project}", styles['Normal']),
        Paragraph(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']),
        Spacer(1, 20),
    ]

    if chart_buffer:
        story.append(Paragraph("Longitudinal Trend", styles['Heading2']))
        story.append(RLImage(chart_buffer, width=450, height=257))
        story.append(Spacer(1, 20))

    if weight_rows:
        story.append(Paragraph("Weight History", styles['Heading2']))
        table_data = [['Date', 'Weight (kg)']] + [[d, w] for d, w in weight_rows]
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

    if exemplar_images:
        story.append(Paragraph("Exemplar QA Images", styles['Heading2']))
        for date_str, path in exemplar_images:
            story.append(Paragraph(date_str, styles['Normal']))
            # Preserve the source image's aspect ratio rather than forcing a fixed box.
            with PILImage.open(path) as im:
                w, h = im.size
            display_width = 300
            display_height = display_width * (h / w)
            story.append(RLImage(path, width=display_width, height=display_height))
            story.append(Spacer(1, 10))

    doc.build(story)

    return send_file(output_path, download_name=f"{patient_id}_report.pdf", as_attachment=True, mimetype="application/pdf")
