"""
Orthanc REST helpers and the data-retention logic for Orthanc-received series.

Orthanc is the long-term store for anything sent over DICOM; /data/inbox is only a scratch
copy for the duration of a series' processing pipeline. Once the pipeline ends (successfully
or not) cleanup_series() removes the inbox copy and - if the sending node's retention rule is
0 days - the series in Orthanc too. Longer retention periods are enforced by the sweeper thread
in orthanc/trigger.py.

Retention rules are keyed on the sending node's AE title (Orthanc's RemoteAET metadata), e.g.
RETENTION_RULES='{"MOSAIQ": 30}', with RETENTION_DEFAULT_DAYS for any node not listed.
"""
import os
import json
import shutil
import logging
import tempfile
from contextlib import contextmanager

import requests

logger = logging.getLogger(__name__)

ORTHANC_URL = "https://orthanc:8042"
ORTHANC_AUTH = (os.environ['ORTHANC_USER'], os.environ['ORTHANC_PASSWORD'])

INBOX_DIR = '/data/inbox'
# Dot-prefixed so it can't collide with a patient ID or Orthanc's own storage directories,
# which share this volume (see docker-compose.yml).
RESTORE_DIR = os.path.join(INBOX_DIR, '.restore')

_RETENTION_RULES = json.loads(os.environ.get('RETENTION_RULES') or '{}')
_RETENTION_DEFAULT_DAYS = float(os.environ.get('RETENTION_DEFAULT_DAYS') or 0)


def retention_days(remote_aet):
    """Days to keep a series in Orthanc, based on the AE title of the node that sent it."""
    return float(_RETENTION_RULES.get((remote_aet or '').strip(), _RETENTION_DEFAULT_DAYS))


#* ===================== REST =====================

def fetch_series(orthanc_series_id, dest_dir):
    """Download every instance of an Orthanc series into dest_dir. Returns the number of instances."""
    os.makedirs(dest_dir, exist_ok=True)

    instances = requests.get(f"{ORTHANC_URL}/series/{orthanc_series_id}/instances", auth=ORTHANC_AUTH, verify=False).json()
    for instance in instances:
        instance_id = instance['ID'] if isinstance(instance, dict) else instance
        main_tags = instance.get('MainDicomTags', {}) if isinstance(instance, dict) else {}
        filename = f"{main_tags.get('SOPInstanceUID', instance_id)}.dcm"

        dest = os.path.join(dest_dir, filename)
        if os.path.isfile(dest):
            continue ## Skip if already fetched (idempotent re-delivery)

        content = requests.get(f"{ORTHANC_URL}/instances/{instance_id}/file", auth=ORTHANC_AUTH, verify=False).content
        with open(dest, 'wb') as f:
            f.write(content)
    return len(instances)


def lookup_series(series_uid):
    """Orthanc's internal ID for a SeriesInstanceUID, or None if Orthanc no longer has it."""
    response = requests.post(f"{ORTHANC_URL}/tools/lookup", data=series_uid, auth=ORTHANC_AUTH, verify=False)
    response.raise_for_status()
    matches = [x['ID'] for x in response.json() if x.get('Type') == 'Series']
    return matches[0] if matches else None


def delete_series(orthanc_series_id):
    response = requests.delete(f"{ORTHANC_URL}/series/{orthanc_series_id}", auth=ORTHANC_AUTH, verify=False)
    if response.status_code == 404:
        logger.info(f"Orthanc series {orthanc_series_id} already deleted")
        return
    response.raise_for_status()
    logger.info(f"Deleted series {orthanc_series_id} from Orthanc")


def delete_series_by_uid(series_uid):
    orthanc_series_id = lookup_series(series_uid)
    if orthanc_series_id is not None:
        delete_series(orthanc_series_id)


#* ===================== RETENTION =====================

def _is_inbox_series_dir(path):
    """
    True only for <INBOX_DIR>/<patient>/<study>/<series>[/...] - the inbox shares its volume with
    Orthanc's own storage, so never delete anything shallower than a single series' directory.
    """
    real = os.path.realpath(path)
    inbox = os.path.realpath(INBOX_DIR)
    if os.path.commonpath([real, inbox]) != inbox:
        return False
    return len(os.path.relpath(real, inbox).split(os.sep)) >= 3


def cleanup_series(ctx):
    """
    Remove a series' inbox copy, and its Orthanc copy too if its retention is 0 days.
    Safe to call more than once.

    ctx: {"inbox_dir": str, "orthanc_series_ids": [str], "retention_days": float, ...}
    """
    inbox_dir = ctx['inbox_dir']
    if not _is_inbox_series_dir(inbox_dir):
        logger.error(f"Refusing to delete {inbox_dir} - not a series directory inside {INBOX_DIR}")
    elif os.path.isdir(inbox_dir):
        shutil.rmtree(inbox_dir)
        logger.info(f"Removed inbox copy: {inbox_dir}")

    if ctx['retention_days'] == 0:
        for orthanc_series_id in ctx['orthanc_series_ids']:
            delete_series(orthanc_series_id)


def on_pipeline_root_failure(job, connection, type, value, traceback):
    """
    RQ on_failure callback for the first job of an Orthanc pipeline (spine for CT, register for
    CBCT). Its dependent segment jobs - and the cleanup job waiting on them - would otherwise
    stay deferred forever (Dependency(allow_failure=True) doesn't count deferred/canceled jobs as
    done), so cancel them and clean up straight away.
    """
    from rq.job import Job
    from rq.exceptions import NoSuchJobError, InvalidJobOperation

    ctx = job.meta['cleanup_ctx']
    for job_id in ctx.get('dependent_job_ids', []):
        try:
            Job.fetch(job_id, connection=connection).cancel()
        except (NoSuchJobError, InvalidJobOperation):
            pass
    cleanup_series(ctx)


@contextmanager
def local_series(input_path, series_uid):
    """
    Yield a local path to a scan's DICOM. If an Orthanc-received scan's inbox copy has already
    been cleaned up, restore it from Orthanc into a temporary directory for the duration of the
    block. Raises ValueError if Orthanc no longer has it either.
    """
    if os.path.exists(input_path):
        yield input_path
        return

    if os.path.commonpath([os.path.realpath(input_path), os.path.realpath(INBOX_DIR)]) != os.path.realpath(INBOX_DIR):
        raise ValueError(f"Source scan not found at {input_path}")

    orthanc_series_id = lookup_series(series_uid)
    if orthanc_series_id is None:
        raise ValueError("Source scan is no longer available - it has been removed from Orthanc under the "
                         "retention policy. Re-send it to use this feature.")

    os.makedirs(RESTORE_DIR, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(dir=RESTORE_DIR)
    try:
        logger.info(f"Restoring series {series_uid} from Orthanc into {tmp_dir}")
        fetch_series(orthanc_series_id, tmp_dir)
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
