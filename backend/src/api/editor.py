"""
Endpoints for the in-browser contour editor.

Serves the raw scan (converted to NIfTI on the fly if needed) and the current/backup
prediction masks (already scan-aligned NIfTI, served as-is) for NiiVue to render, and
accepts an edited mask upload, writing it to the canonical mask path. Recomputing stats
from a saved mask reuses the existing, unmodified `POST /api/database/extract_stats_from_mask`
endpoint - this blueprint only serves/saves files.

'total_muscle' is presented as the editable "muscle" compartment (IMAT is never a native
model output - it's always derived from skeletal_muscle, see segmentationEngine.extract_imat)
but it's a real, persisted file: engine.py's forward()/forward_extract_stats() both write
masks/<vertebra>/total_muscle.nii.gz (the network's true, un-holed muscle prediction) before
IMAT gets carved out of it, so this blueprint treats it exactly like any other compartment.
"""
import os
import logging
import tempfile
import SimpleITK as sitk
from flask import Blueprint, request, make_response, jsonify, send_file, abort

from app import mongo
from abcTK.inference.segment import get_loader_function
from abcTK.segment.model_bank import model_bank

bp = Blueprint('api/editor', __name__)
logger = logging.getLogger(__name__)


#* ===================== HELPERS =====================

def _get_segmentation_entry(project, _id):
    entry = mongo.db.segmentation.find_one({"_id": _id, "project": project})
    if entry is None:
        abort(404, {"message": f"No segmentation entry found for _id={_id}, project={project}"})
    return entry


def _get_modality(project, _id):
    image = mongo.db.images.find_one({"_id": _id, "project": project})
    if image is None or not image.get('modality'):
        abort(404, {"message": f"No modality found for _id={_id}, project={project}"})
    return image['modality']


def _valid_compartments(vertebra, modality):
    # Source of truth for "which compartments exist at this vertebra/modality" - also
    # doubles as the security boundary since vertebra/compartment feed directly into
    # filesystem paths below. Always call this (and check membership) before building
    # any mask path from client-supplied vertebra/compartment values.
    if vertebra not in model_bank or modality not in model_bank[vertebra]:
        abort(400, {"message": f"No model for vertebra={vertebra}, modality={modality}"})
    compartments = [x for x in model_bank[vertebra][modality]['segments'].keys() if x != 'background']
    # 'skeletal_muscle' is presented (and addressed by callers) as 'total_muscle' - see
    # module docstring.
    return ['total_muscle' if x == 'skeletal_muscle' else x for x in compartments]


#* ===================== API =====================

@bp.route('/api/editor/get_metadata', methods=["GET"])
def get_metadata():
    project = request.args.get("project")
    _id = request.args.get("_id")
    vertebra = request.args.get("vertebra")

    entry = _get_segmentation_entry(project, _id)
    modality = _get_modality(project, _id)
    compartments = _valid_compartments(vertebra, modality)

    mask_dir = os.path.join(entry['output_dir'], 'masks', vertebra)
    data = []
    for compartment in compartments:
        canonical = os.path.join(mask_dir, f'{compartment}.nii.gz')
        backup = os.path.join(mask_dir, f'{compartment}_original.nii.gz')
        item = {
            "name": compartment,
            "has_mask": os.path.isfile(canonical),
            "has_backup": os.path.isfile(backup),
        }
        if item["has_backup"]:
            # Frontend must never construct filesystem paths itself - hand back the exact
            # path to use as `mask_path` when calling extract_stats_from_mask to revert.
            item["original_mask_path"] = backup
        data.append(item)

    res = make_response(jsonify({
        "message": "Successfully collected editor metadata",
        "vertebra": vertebra,
        "modality": modality,
        "input_path": entry['input_path'],
        "compartments": data
    }), 200)
    return res


@bp.route('/api/editor/scan', methods=["GET"])
def get_scan():
    project = request.args.get("project")
    _id = request.args.get("_id")
    refresh = request.args.get("refresh", "0").lower() in ('1', 'true', 'yes')

    entry = _get_segmentation_entry(project, _id)
    input_path = entry['input_path']
    output_dir = entry['output_dir']

    # If the scan is already a single-file NIfTI/NRRD, serve it directly - it's already
    # exactly what NiiVue needs, no conversion or caching required.
    if os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[-1].lower()
        if ext in ('.nii', '.gz', '.nrrd'):
            return send_file(input_path, mimetype='application/octet-stream')

    # Otherwise (a DICOM series directory) convert once via the existing loader and cache
    # the result alongside this series' other outputs, since re-reading/re-converting a
    # full DICOM series on every editor page load would be slow.
    cache_dir = os.path.join(output_dir, 'editor_cache')
    cache_path = os.path.join(cache_dir, 'scan.nii.gz')

    if refresh and os.path.isfile(cache_path):
        os.remove(cache_path)

    if not os.path.isfile(cache_path):
        loader_function, _ = get_loader_function(input_path)
        image = loader_function(input_path)
        os.makedirs(cache_dir, exist_ok=True)
        sitk.WriteImage(image, cache_path)

    return send_file(cache_path, mimetype='application/octet-stream')


@bp.route('/api/editor/mask', methods=["GET"])
def get_mask():
    project = request.args.get("project")
    _id = request.args.get("_id")
    vertebra = request.args.get("vertebra")
    compartment = request.args.get("compartment")
    variant = request.args.get("variant", "current")

    entry = _get_segmentation_entry(project, _id)
    modality = _get_modality(project, _id)
    if compartment not in _valid_compartments(vertebra, modality):
        abort(400, {"message": f"Unrecognised compartment '{compartment}' for vertebra={vertebra}, modality={modality}"})

    mask_dir = os.path.join(entry['output_dir'], 'masks', vertebra)
    suffix = '_original' if variant == 'original' else ''
    path = os.path.join(mask_dir, f'{compartment}{suffix}.nii.gz')
    if not os.path.isfile(path):
        abort(404, {"message": f"No mask found at {path}"})

    return send_file(path, mimetype='application/octet-stream')


@bp.route('/api/editor/save_mask', methods=["POST"])
def save_mask():
    project = request.form.get("project")
    _id = request.form.get("_id")
    vertebra = request.form.get("vertebra")
    compartment = request.form.get("compartment")

    if 'mask' not in request.files:
        raise ValueError("No mask file was uploaded. Attach it under the 'mask' form field.")

    entry = _get_segmentation_entry(project, _id)
    modality = _get_modality(project, _id)
    if compartment not in _valid_compartments(vertebra, modality):
        raise ValueError(f"Unrecognised compartment '{compartment}' for vertebra={vertebra}, modality={modality}")

    mask_dir = os.path.join(entry['output_dir'], 'masks', vertebra)
    os.makedirs(mask_dir, exist_ok=True)
    canonical_path = os.path.join(mask_dir, f'{compartment}.nii.gz')

    # Write the upload to a temp file in the same directory first and validate it's a
    # well-formed image before it's allowed to become the canonical file - defends
    # against a corrupt/partial upload clobbering good data. os.replace is atomic since
    # both paths are on the same filesystem/mount.
    fd, tmp_path = tempfile.mkstemp(dir=mask_dir, suffix='.nii.gz')
    os.close(fd)
    try:
        request.files['mask'].save(tmp_path)
        sitk.ReadImage(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        raise ValueError(f"Uploaded mask could not be read as an image: {e}")

    os.replace(tmp_path, canonical_path)

    res = make_response(jsonify({
        "message": "Mask saved",
        "mask_path": canonical_path,
        "input_path": entry['input_path']
    }), 200)
    return res
