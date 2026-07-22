"""
Registration job.

Used to compute the rigid transform aligning a "moving" scan (e.g. a CBCT with no exportable
registration object from the R&V system) onto an already spine-labelled "fixed" scan (e.g. its
planning CT).

The fixed and moving scans are not assumed to share a coordinate frame of reference (they may
come from completely different machines/rooms), so alignment relies entirely on image content
(mutual information + automatic centre-of-gravity initialisation), not on the two scans'
DICOM-header physical coordinates already corresponding to one another.

This deliberately never writes to mongo.db.spine - that collection is the model's own
vertebra-labelling output and should stay unambiguous. The computed transform is written to a
separate mongo.db.registration collection, keyed by the *moving* scan's own series_uuid.

Once the moving scan is resampled through this transform onto the fixed scan's grid (via
abcTK/segment/engine.py::segmentationEngine.apply_transform, the same function used for a real
DICOM Spatial Registration Object), it shares the fixed scan's geometry exactly - so the fixed
scan's own vertebra slice indices (mongo.db.spine's `prediction`) are then directly valid on it.
abcTK/inference/segment.py::handle_request is what wires the transform in for that reuse case.
"""
import os
import logging

import numpy as np
import SimpleITK as sitk
import itk
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from abcTK.inference.segment import get_loader_function, check_params
from abcTK.segment.engine import segmentationEngine

logger = logging.getLogger(__name__)

# Rotation magnitude above which the registration result is flagged for manual review.
# Rotation (unlike translation) is meaningful to gate on here even though the fixed/moving
# scans may come from different machines with unrelated coordinate origins: it reflects a
# genuine change in patient orientation between the two scans, not an arbitrary frame offset.
ROTATION_WARNING_DEG = 20.0


def infer_register(req):
    from app import mongo

    logger.info(f"Registration request received: {req}")
    check_params(req, required_params=["input_path", "project", "patient_id", "series_uuid", "reference_scan"])

    pct_spine = mongo.db.spine.find_one({"_id": req['reference_scan']})
    if pct_spine is None:
        raise ValueError(f"No labelled planning CT found for reference_scan: {req['reference_scan']}")

    # Fail fast: abcTK/segment/engine.py's reference_scan resolution needs this record to exist
    # (Origin/Spacing/Direction/Size) once the segment job actually runs.
    if mongo.db.images.find_one({"_id": req['reference_scan']}) is None:
        raise ValueError(f"No image record found for reference_scan: {req['reference_scan']}")

    output_dir = os.path.join(req['APP_OUTPUT_DIR'], req['project'], req['patient_id'], req['series_uuid'])
    os.makedirs(output_dir, exist_ok=True)

    moving_loader, _ = get_loader_function(req['input_path'])
    moving_image = moving_loader(req['input_path'])  # e.g. CBCT

    fixed_loader, _ = get_loader_function(pct_spine['input_path'])
    fixed_image = fixed_loader(pct_spine['input_path'])  # planning CT

    logger.info(
        f"Registering moving scan ({req['input_path']}, size {moving_image.GetSize()}, spacing {moving_image.GetSpacing()}) "
        f"onto fixed scan ({pct_spine['input_path']}, size {fixed_image.GetSize()}, spacing {fixed_image.GetSpacing()})"
    )

    fixed_to_moving, metrics = register_rigid(fixed_image, moving_image, log_dir=output_dir)

    # Persist the moving->fixed transform to disk, in the convention already used by
    # abcTK/segment/engine.py::read_transform/apply_transform (i.e. it maps a point in the
    # *moving* scan onto the corresponding point in the *fixed* scan's space), so it can be
    # consumed by that existing pathway without any change to those functions.
    moving_to_fixed = fixed_to_moving.GetInverse()
    transform_path = os.path.join(output_dir, 'registration.tfm')
    sitk.WriteTransform(moving_to_fixed, transform_path)

    if metrics['rotation_deg'] > ROTATION_WARNING_DEG:
        logger.warning(
            f"Registration rotation ({metrics['rotation_deg']:.1f} deg) for {req['series_uuid']} is larger than "
            f"expected for a genuine patient orientation change - review the QC overlay before trusting downstream "
            f"segmentation."
        )

    qc_image_paths = write_registration_qc(output_dir, fixed_image, moving_image, moving_to_fixed, pct_spine['prediction'])

    registration_update = {
        "_id": req['series_uuid'],
        "project": req['project'],
        "patient_id": req['patient_id'],
        "series_uuid": req['series_uuid'],
        "reference_scan": req['reference_scan'],
        "input_path": req['input_path'],
        "output_dir": output_dir,
        "transform_path": transform_path,
        "rotation_deg": metrics['rotation_deg'],
        "qc_image_paths": qc_image_paths,
    }
    mongo.db.registration.update_one({"_id": req['series_uuid']}, {"$set": registration_update}, upsert=True)
    logger.info(f"Inserted {registration_update} into collection: registration")

    return registration_update


########################################################
#* =============== HELPER FUNCTIONS =====================
########################################################

def register_rigid(fixed_image, moving_image, downsample_spacing=(3.0, 3.0, 3.0), log_dir=None):
    """
    Rigid registration of moving_image onto fixed_image using itk-elastix.

    Fixed/moving are not assumed to share a coordinate frame of reference (they may come from
    different machines), so this relies on mutual information (robust to the CT/CBCT intensity
    mismatch, no pre-normalisation required) plus elastix's automatic centre-of-gravity
    initialisation (handles an arbitrary initial offset between the two coordinate frames).

    Registration is run on a downsampled copy of both volumes for speed; the resulting rigid
    transform is a physical-space transform, valid at any resolution, and is returned/applied
    against the full-resolution volumes by the caller.

    Returns (fixed_to_moving transform as sitk.Euler3DTransform, metrics dict).
    """
    fixed_ds, _ = _resample_isotropic(fixed_image, downsample_spacing)
    moving_ds, _ = _resample_isotropic(moving_image, downsample_spacing)

    # Pre-align the two volumes' geometric centres before handing them to elastix, as a
    # deterministic, auditable guarantee of overlap - fixed/moving may come from different
    # machines with arbitrarily distant coordinate origins, and this doesn't rely on elastix's
    # own (less transparent) AutomaticTransformInitializationMethod=CenterOfGravity heuristic to
    # find that overlap on its own. It's a pure Origin-metadata edit (no resampling/
    # interpolation), so it costs nothing and loses no image quality. The shift is subtracted
    # back out of the final result below so the returned transform is correct relative to the
    # original (unshifted) images.
    fixed_center = np.array(fixed_ds.TransformContinuousIndexToPhysicalPoint(np.array(fixed_ds.GetSize()) / 2.0))
    moving_center = np.array(moving_ds.TransformContinuousIndexToPhysicalPoint(np.array(moving_ds.GetSize()) / 2.0))
    center_shift = fixed_center - moving_center

    moving_shifted = sitk.Image(moving_ds)
    moving_shifted.SetOrigin(tuple(np.array(moving_ds.GetOrigin()) + center_shift))

    # A planning CT's FOV is typically much larger than a CBCT's (especially for H&N, where the
    # on-board imager's FOV can be quite small). elastix's default sampler draws samples across
    # the *entire* fixed image and checks whether they land inside the moving image after the
    # current transform estimate - if the fixed image is much bigger than the moving image, most
    # samples miss entirely and elastix fails outright ("Too many samples map outside moving
    # image buffer"), rather than degrading gracefully. Cropping the fixed image down to a region
    # comfortably covering the moving image's own extent (centred on the same pre-alignment
    # point, with a safety margin for residual misalignment) fixes this - verified empirically
    # against a synthetic large-pCT/small-CBCT-sized case that reproduced the failure without
    # this crop and resolved it with it.
    fixed_cropped = _crop_fixed_to_moving_extent(fixed_ds, moving_ds, fixed_center)

    fixed_itk = _sitk_to_itk(fixed_cropped)
    moving_itk = _sitk_to_itk(moving_shifted)

    parameter_object = itk.ParameterObject.New()
    rigid_map = parameter_object.GetDefaultParameterMap('rigid')
    rigid_map['AutomaticTransformInitialization'] = ['true']
    rigid_map['AutomaticTransformInitializationMethod'] = ['CenterOfGravity']
    rigid_map['Metric'] = ['AdvancedMattesMutualInformation']
    parameter_object.AddParameterMap(rigid_map)

    elastix_log_dir = os.path.join(log_dir, 'elastix_log') if log_dir else '/tmp'
    os.makedirs(elastix_log_dir, exist_ok=True)
    try:
        _, result_transform_parameters = itk.elastix_registration_method(
            fixed_itk, moving_itk, parameter_object=parameter_object,
            log_to_console=False, log_to_file=True, output_directory=elastix_log_dir
        )
    except RuntimeError as e:
        raise RuntimeError(f"{e}\nSee the full elastix log at {elastix_log_dir}/elastix.log") from e

    # elastix's own convention: this transform maps a FIXED-space point onto the corresponding
    # point in moving_shifted's space (used natively for pull-resampling moving_shifted into the
    # fixed grid). This is the OPPOSITE direction to abcTK/segment/engine.py::read_transform's
    # convention (moving->fixed) - inverted by the caller before it's persisted/applied.
    params = [float(x) for x in result_transform_parameters.GetParameter(0, 'TransformParameters')]
    center = [float(x) for x in result_transform_parameters.GetParameter(0, 'CenterOfRotationPoint')]
    rot_x, rot_y, rot_z, tx, ty, tz = params

    # Euler3DTransform.TransformPoint(p) = R * (p - center) + center + translation, so
    # subtracting center_shift from the translation component alone (same rotation, same centre)
    # is exactly equivalent to composing with the inverse of the pre-alignment shift - i.e. this
    # yields the fixed->moving_shifted transform re-expressed as fixed->(original) moving.
    translation = np.array((tx, ty, tz)) - center_shift

    fixed_to_moving = sitk.Euler3DTransform()
    fixed_to_moving.SetCenter(center)
    fixed_to_moving.SetRotation(rot_x, rot_y, rot_z)
    fixed_to_moving.SetTranslation(tuple(translation))

    rotation_deg = float(np.degrees(np.linalg.norm([rot_x, rot_y, rot_z])))
    logger.info(f"Registration result - rotation: {rotation_deg:.2f} deg, translation: {tuple(translation)} mm")

    return fixed_to_moving, {"rotation_deg": rotation_deg}


def write_registration_qc(output_dir, fixed_image, moving_image, moving_to_fixed, fixed_centroids):
    """
    Writes one side-by-side (pCT slice | registered moving-scan slice, resampled onto the pCT's
    own grid exactly as abcTK/segment/engine.py::apply_transform will do for segmentation)
    overlay image per vertebra level, for mandatory human visual review before the registration
    result is trusted.
    """
    reference_info = {
        'Origin': fixed_image.GetOrigin(), 'Spacing': fixed_image.GetSpacing(),
        'Direction': fixed_image.GetDirection(), 'Size': fixed_image.GetSize(),
    }
    resampled_moving = segmentationEngine.apply_transform(moving_image, moving_to_fixed, reference_info)

    fixed_array = sitk.GetArrayFromImage(fixed_image)
    moving_array = sitk.GetArrayFromImage(resampled_moving)

    qc_dir = os.path.join(output_dir, 'sanity', 'registration')
    os.makedirs(qc_dir, exist_ok=True)

    paths = {}
    for level, centroid in fixed_centroids.items():
        slice_number = int(round(centroid[-1]))
        if not (0 <= slice_number < moving_array.shape[0]):
            continue

        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        fig.patch.set_facecolor('black')
        ax[0].imshow(fixed_array[slice_number], cmap='gray')
        ax[0].set_title(f'Planning CT - {level} (slice {slice_number})', c='white')
        ax[1].imshow(moving_array[slice_number], cmap='gray')
        ax[1].set_title(f'Moving scan - registered (slice {slice_number})', c='white')
        for a in ax:
            a.axis('off')

        output_filename = os.path.join(qc_dir, f'{level}.png')
        fig.savefig(output_filename, facecolor='black')
        plt.close(fig)
        paths[level] = output_filename

    return paths


def _crop_fixed_to_moving_extent(fixed_image, moving_image, fixed_center, margin=1.5):
    """
    Crops fixed_image to a box centred on fixed_center, sized to comfortably cover
    moving_image's own physical extent (with a safety margin for residual misalignment beyond
    the centre-of-gravity pre-alignment). See register_rigid's docstring for why this is needed.
    """
    moving_extent = np.array(moving_image.GetSize()) * np.array(moving_image.GetSpacing())
    half_extent = (moving_extent * margin) / 2.0

    lower_index = np.array(fixed_image.TransformPhysicalPointToContinuousIndex(tuple(fixed_center - half_extent)))
    upper_index = np.array(fixed_image.TransformPhysicalPointToContinuousIndex(tuple(fixed_center + half_extent)))
    start = np.maximum(np.minimum(lower_index, upper_index), 0).astype(int)
    stop = np.minimum(np.maximum(lower_index, upper_index), np.array(fixed_image.GetSize()) - 1).astype(int)
    size = np.maximum(stop - start, 1).tolist()

    roi = sitk.RegionOfInterestImageFilter()
    roi.SetIndex([int(x) for x in start])
    roi.SetSize([int(x) for x in size])
    return roi.Execute(fixed_image)


def _resample_isotropic(image, spacing):
    resample = sitk.ResampleImageFilter()
    resample.SetInterpolator(sitk.sitkLinear)
    resample.SetOutputDirection(image.GetDirection())
    resample.SetOutputOrigin(image.GetOrigin())
    ratio = tuple(x / y for x, y in zip(image.GetSpacing(), spacing))
    new_size = [int(np.round(x * s)) for x, s in zip(image.GetSize(), ratio)]
    resample.SetSize(new_size)
    resample.SetOutputSpacing(spacing)
    resample.SetDefaultPixelValue(-1024)
    return resample.Execute(image), ratio


def _sitk_to_itk(image):
    array = sitk.GetArrayFromImage(image).astype(np.float32)
    itk_image = itk.GetImageFromArray(array)
    itk_image.SetSpacing(image.GetSpacing())
    itk_image.SetOrigin(image.GetOrigin())
    direction = np.array(image.GetDirection()).reshape(3, 3)
    itk_image.SetDirection(itk.matrix_from_array(direction))
    return itk_image
