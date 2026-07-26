"""
Orthanc Python plugin trigger.

Fires when a series has finished arriving (StableAge seconds without a new instance) and posts
the same set of DICOM header values Conquest's trigger.lua used to, to the backend's
/api/orthanc/handle_trigger endpoint, so it can pull the series over Orthanc's REST API and
enqueue the appropriate spine/segment/register jobs.
"""
import json

import orthanc
import requests

BACKEND_URL = "https://backend:5001/api/orthanc/handle_trigger"


def on_change(change_type, level, resource_id):
    if change_type != orthanc.ChangeType.STABLE_SERIES:
        return

    series = json.loads(orthanc.RestApiGet(f"/series/{resource_id}"))
    study = json.loads(orthanc.RestApiGet(f"/studies/{series['ParentStudy']}"))
    patient = json.loads(orthanc.RestApiGet(f"/patients/{study['ParentPatient']}"))

    instance_id = series["Instances"][0]
    instance_tags = json.loads(orthanc.RestApiGet(f"/instances/{instance_id}/simplified-tags"))
    manufacturer_model_name = instance_tags.get("ManufacturerModelName", "")

    params = {
        "series_uid": series["MainDicomTags"]["SeriesInstanceUID"],
        "study_uid": study["MainDicomTags"]["StudyInstanceUID"],
        "patient_id": patient["MainDicomTags"]["PatientID"],
        "modality": series["MainDicomTags"]["Modality"],
        "manufacturer_model_name": manufacturer_model_name,
        "orthanc_series_id": resource_id,
    }
    orthanc.LogWarning(f"Stable series trigger firing: {params}")

    # ssl/cert.crt has no Subject Alternative Name, so strict verification against it always
    # fails regardless of hostname - every other internal service-to-service call in this
    # codebase already disables verification for that reason (e.g. api/orthanc.py's own calls
    # to the spine/segment/register endpoints), matched here for consistency.
    response = requests.post(BACKEND_URL, params=params, verify=False)
    if not response.ok:
        orthanc.LogError(f"handle_trigger call failed ({response.status_code}): {response.text}")


orthanc.RegisterOnChangeCallback(on_change)
