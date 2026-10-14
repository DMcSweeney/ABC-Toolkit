"""
Orthanc Python plugin trigger.

Fires when a series has finished arriving (StableAge seconds without a new instance) and posts
the same set of DICOM header values Conquest's trigger.lua used to, to the backend's
/api/orthanc/handle_trigger endpoint, so it can pull the series over Orthanc's REST API and
enqueue the appropriate spine/segment/register jobs.

Also runs the retention sweeper: series whose sending node (RemoteAET) has a retention period
in RETENTION_RULES are deleted once they're older than it. Series with 0 days' retention are
deleted by the backend as soon as their pipeline finishes (see backend abcTK/orthanc_client.py).
"""
import os
import json
import datetime
import threading

import orthanc
import requests

BACKEND_URL = "https://backend:5001/api/orthanc/handle_trigger"

# Same lookup as backend abcTK/orthanc_client.py::retention_days - duplicated since this
# container can't import backend code.
RETENTION_RULES = json.loads(os.environ.get('RETENTION_RULES') or '{}')
RETENTION_DEFAULT_DAYS = float(os.environ.get('RETENTION_DEFAULT_DAYS') or 0)
SWEEP_INTERVAL_SECONDS = float(os.environ.get('RETENTION_SWEEP_INTERVAL_SECONDS') or 3600)

_stop_sweeper = threading.Event()


def retention_days(remote_aet):
    return float(RETENTION_RULES.get((remote_aet or '').strip(), RETENTION_DEFAULT_DAYS))


def get_remote_aet(instance_id):
    # Instances uploaded over REST (rather than C-STORE) have no RemoteAET
    try:
        return orthanc.RestApiGet(f"/instances/{instance_id}/metadata/RemoteAET").decode().strip()
    except orthanc.OrthancException:
        return ""


def on_stable_series(resource_id):
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
        "remote_aet": get_remote_aet(instance_id),
    }
    orthanc.LogWarning(f"Stable series trigger firing: {params}")

    # ssl/cert.crt has no Subject Alternative Name, so strict verification against it always
    # fails regardless of hostname - every other internal service-to-service call in this
    # codebase already disables verification for that reason (e.g. api/orthanc.py's own calls
    # to the spine/segment/register endpoints), matched here for consistency.
    response = requests.post(BACKEND_URL, params=params, verify=False)
    if not response.ok:
        orthanc.LogError(f"handle_trigger call failed ({response.status_code}): {response.text}")


def sweep_expired_series():
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)  # LastUpdate is UTC
    all_series = json.loads(orthanc.RestApiPost("/tools/find", json.dumps({"Level": "Series", "Query": {}, "Expand": True})))
    for series in all_series:
        if not series.get("Instances"):
            continue
        remote_aet = get_remote_aet(series["Instances"][0])
        days = retention_days(remote_aet)
        if days == 0:
            continue  # Deleted by the backend once processed

        last_update = datetime.datetime.strptime(series["LastUpdate"], "%Y%m%dT%H%M%S")
        if now - last_update > datetime.timedelta(days=days):
            orthanc.LogWarning(f"Retention: deleting series {series['ID']} from {remote_aet or 'unknown sender'} "
                               f"(last updated {last_update}, retention {days} days)")
            orthanc.RestApiDelete(f"/series/{series['ID']}")


def sweeper_loop():
    while not _stop_sweeper.wait(SWEEP_INTERVAL_SECONDS):
        try:
            sweep_expired_series()
        except Exception as e:
            orthanc.LogError(f"Retention sweep failed: {e}")


def on_change(change_type, level, resource_id):
    if change_type == orthanc.ChangeType.STABLE_SERIES:
        on_stable_series(resource_id)
    elif change_type == orthanc.ChangeType.ORTHANC_STARTED:
        threading.Thread(target=sweeper_loop, daemon=True).start()
    elif change_type == orthanc.ChangeType.ORTHANC_STOPPED:
        _stop_sweeper.set()


orthanc.RegisterOnChangeCallback(on_change)
