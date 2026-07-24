# API Reference

This is a complete reference for every HTTP endpoint exposed by the ABC-Toolkit backend (`backend/src/api/*.py` and `backend/src/main.py`).

**Base URL:** `https://<HOST_IP>:<BACKEND_PORT>` (HTTPS, self-signed cert — see [ssl/README.md](../ssl/README.md); pass `--insecure`/`verify=False` in clients). Default in `.env-default`: `https://localhost:5001`.

**Request format:** `POST` endpoints take a JSON body (`Content-Type: application/json`) unless noted otherwise. `GET` endpoints take query-string parameters. A few endpoints mix both (JSON body **and** query string) — called out explicitly below.

**Response format:** All endpoints return JSON (`{"message": ..., ...}`) except where noted (e.g. CSV/DICOM file downloads).

**Argument value quirks worth knowing up front:**
- Booleans are usually sent as the *strings* `"True"`/`"False"` (or `"1"`/`"0"`/`"yes"`/`"no"`) in a JSON body, then converted server-side — not JSON `true`/`false`.
- A few flags (`for_editing`, `download`) are compared with `== 'True'` literally — any other value, including `"False"`, is treated as false. Passing a JSON boolean `true` instead of the string `"True"` will silently be treated as false.
- `_id` almost always refers to a **series-level** Mongo document id (in practice the DICOM `series_uuid`), not a patient id — collections are keyed by series (`images`, `spine`, `segmentation`, `quality_control` all share `_id = series_uuid`).
- **Errors** come back as `{"error": "<message>"}` with a `4xx`/`5xx` status (a global handler normalizes this, so you get a real message instead of a raw traceback even from endpoints that don't build the response themselves). A handful of older endpoints instead return their own `{"message": ..., "data": null}` shape on a deliberate `4xx` — if you're writing a generic client-side error handler, check for both keys.

Runnable examples for most endpoints below live in [examples/api/](../examples/api/) (curl) and [examples/python/](../examples/python/).

---

## Table of contents

- [Health check](#health-check)
- [Jobs — `/api/jobs`](#jobs--apijobs)
- [Conquest (DICOM ingestion) — `/api/conquest`](#conquest-dicom-ingestion--apiconquest)
- [Database — `/api/database`](#database--apidatabase)
- [Post-processing — `/api/post_process`](#post-processing--apipost_process)
- [Sanity QA (legacy, per-vertebra) — `/api/sanity`](#sanity-qa-legacy-per-vertebra--apisanity)
- [Patient QA (per-compartment) — `/api/patient_qa`](#patient-qa-per-compartment--apipatient_qa)
- [Weights — `/api/weights`](#weights--apiweights)
- [RQ Dashboard](#rq-dashboard)

---

## Health check

### `GET /hello`
No args. Returns `{"message": "Welcome", "sender": "ABC"}`. Useful for confirming the backend container is reachable.

---

## Jobs — `/api/jobs`

Job endpoints don't run inference inline — they enqueue work onto Redis/RQ and return immediately with a `job-ID`. Actual processing happens in the `gpu-workers` (queue `high`) / `cpu-workers` (queues `default`, `low`) containers. See [CLAUDE.md](../CLAUDE.md) for the queueing architecture.

### `POST /api/jobs/infer/spine`
Enqueues a vertebra-labelling job (queue `high`, GPU only, 300s timeout). Body → passed straight through as the job's `req` dict, plus extra fields filled in from the DICOM/NIfTI header and defaults (see `abcTK/inference/spine.py::handle_request`).

| Arg | Required | Type | Default | Description |
|---|---|---|---|---|
| `input_path` | yes | string | — | Path to the scan **as seen inside the container** (e.g. `/data/inputs/...`), either a DICOM directory or a `.nii`/`.nii.gz`/`.npy`/`.npz` file. |
| `project` | yes | string | — | Project name; groups results together (auto-created on first use, not a separate "create project" call). |
| `patient_id` | no | string | read from DICOM tag `(0010,0020)` | Required if not derivable from the header (e.g. NIfTI/numpy input) — request fails with a `ValueError` otherwise. |
| `series_uuid` | no | string | read from DICOM tag `(0020,000e)`, or filtered to that series if a DICOM directory contains multiple series | Required if not derivable from the header. |
| `worldmatch_correction` | no | string bool | `"False"` | Whether to shift intensities by −1024 HU (needed for scans that have been through Elekta CT-to-density "worldmatch" processing). |
| `modality` | no | string | `"CT"` | Spine labelling **only supports `"CT"`** — any other value raises an error. |

Note: `patient_id`/`series_uuid` etc. can also just be passed explicitly in the body to skip/override header parsing — any key already present in `req` is left alone and the header value is ignored (logged as "provided in request, ignoring DICOM header").

**Response:** `{"message": ..., "request": <the resolved request dict>, "job-ID": <rq job id>}`. Use `GET /api/jobs/query_job` to poll for completion — on success, results are written to the `spine`, `images`, and `quality_control` Mongo collections (not returned in this response).

### `POST /api/jobs/infer/segment`
Enqueues a tissue-segmentation job for **one image, one vertebral level, one modality** (queue `default`; make multiple requests for multiple levels). Body → passed through to `abcTK/inference/segment.py::handle_request` for defaulting/validation.

| Arg | Required | Type | Default | Description |
|---|---|---|---|---|
| `input_path` | yes | string | — | Same as spine endpoint. |
| `project` | yes | string | — | Same as spine endpoint. |
| `vertebra` | conditionally | string | — | One of the levels in `model_bank` (`C3, T4, T9, T12, L3, L5, Sacrum, Thigh`). **If omitted**, the endpoint (not the worker) looks up every level in `abcTK/segment/model_bank.py` that has a model for `req['modality']` and submits **one job per level** — but this requires `modality` to already be present in the request body at submit time (it is *not* defaulted to `"CT"` until inside the worker), so omitting both `vertebra` and `modality` together will error. |
| `patient_id` | no | string | from DICOM header | Same caveat as spine endpoint. |
| `series_uuid` | no | string | from DICOM header | Same caveat as spine endpoint. |
| `depends_on` | no | string (RQ job id) | `None` | Makes this job wait for another job (typically the matching spine-labelling job) to finish first. This is how the two-step spine→segment pipeline is chained (see [examples/python/submit_jobs.py](../examples/python/submit_jobs.py)). |
| `modality` | no | string | `"CT"` (defaulted inside the worker, see `vertebra` caveat above) | One of `CT, CBCT, MR, LowDoseCT` depending on what `model_bank.py` defines for the chosen vertebra. |
| `slice_number` | conditionally | int (or numeric string) | looked up from the `spine` collection | Required unless a prior spine-labelling job (matched by `series_uuid`, or by `reference_scan` if given) has already recorded a prediction for `vertebra`. **If `reference_scan` is given and differs from `series_uuid`** (i.e. this scan is reusing another scan's labelling, e.g. a CBCT reusing its planning CT's), that reused slice number is only meaningful once this scan has actually been resampled onto the reference scan's own grid — so a prior `infer/register` job (see below) must have completed first (chain it with `depends_on`), and its output `transform_path` is picked up automatically from the `registration` collection to do that resampling (equivalent to passing `resample_transform` yourself); the request fails if no registration record is found for this `series_uuid`. If you pass `slice_number` explicitly, `override_spine_sanity` is forced to `True` (a new single-level spine QA image is generated instead of reusing the full-spine one). |
| `num_slices` | no | int (or numeric string) | `0` | How many extra slices to segment on either side of `slice_number` (e.g. `1` → 3 total slices). |
| `worldmatch_correction` | no | string bool | `"False"` | Same as spine endpoint. |
| `generate_bone_mask` | no | string bool, or a path string | `True` | `False`/`"False"` skips regenerating the bone mask (faster); a non-boolean string is treated as a path to an existing bone mask to reuse. |
| `muscle_threshold` / `fat_threshold` | no | string tuple, e.g. `"(-29, 150)"` | `(-29, 150)` / `(-190, -30)` HU | HU clipping range for skeletal muscle / fat compartments. Elements can be `"None"` to disable that bound. |

**CBCT and registration args** (niche — most CT requests don't need these): `resample` (bool, needs at least one of `resample_spacing`/`resample_transform`/`reference_scan`), `reference_scan` (Mongo `_id` of another scan/spine-entry to align to), `calibrate_cbct` (bool, requires `reference_scan` + `calibration_structure` naming the ROI to calibrate against, and ignores `scale_intensity` if both are given), `scale_intensity`/`shift_intensity` (manual intensity rescale/shift, alternative to `calibrate_cbct`), `override_spine_sanity` (bool, regenerate a single-level spine QA image instead of reusing the full-spine one — automatically forced on if you pass `slice_number` explicitly). See `abcTK/segment/engine.py` and the CBCT example in [examples/api/jobs/queue_infer_segment.sh](../examples/api/jobs/queue_infer_segment.sh) for how these combine in practice.

**Response:** if `vertebra` was given, `{"message": ..., "request": ..., "level": <vertebra>, "job-ID": <id>}`; if omitted, `"level"` and `"job-ID"` are lists (one per matched model). **Note:** the underlying worker function (`infer_segment`) has no `return` statement, so `GET /api/jobs/query_job` will report the result as the string `"None"` on success — check the `segmentation`/`quality_control` Mongo collections or the post-processing endpoints for actual output.

### `POST /api/jobs/infer/register`
Enqueues a rigid image-registration job (queue `low`, CPU only — deliberately kept off the `default` queue so it can't delay other patients' `infer/segment` jobs sharing that pool, 300s timeout). Aligns a "moving" scan (e.g. a CBCT) onto an already spine-labelled "fixed" scan (e.g. its planning CT) using `itk-elastix` (mutual-information rigid registration with automatic centre-of-gravity initialisation — the two scans are **not** assumed to share a coordinate frame, since e.g. a CBCT from a linac's on-board imager and its planning CT from a separate CT simulator generally don't). See `abcTK/inference/register.py`.

| Arg | Required | Type | Description |
|---|---|---|---|
| `input_path` | yes | string | Path to the moving scan (as seen inside the container), same conventions as `infer/spine`. |
| `project` | yes | string | Same as other job endpoints. |
| `patient_id` | yes | string | Same as other job endpoints (not read from a DICOM header here — must be supplied). |
| `series_uuid` | yes | string | The moving scan's own series id — this is the `_id` results are written under. |
| `reference_scan` | yes | string | Mongo `_id` (series_uuid) of an **already spine-labelled** scan (i.e. it must already have an entry in the `spine` collection) to register onto. |

**Response:** `{"message": ..., "request": ..., "job-ID": <rq job id>}`. On success, writes one document to a new `registration` Mongo collection, keyed by the moving scan's `series_uuid`: `{reference_scan, transform_path, rotation_deg, qc_image_paths}`. It never writes to the `spine` collection — the reference scan's own labelling is left untouched and is what `infer/segment` still uses for the actual slice number, once this transform has resampled the moving scan onto the reference scan's own grid (via `apply_transform` in `abcTK/segment/engine.py`, the same mechanism used for a real DICOM Spatial Registration Object). `qc_image_paths` points to one side-by-side (planning CT slice | registered moving-scan slice, on the same resampled grid the segmentation step will actually use) PNG per vertebra level — **inspect these before trusting the result**, especially since there's no automated translation-magnitude sanity check (translation isn't meaningful to gate on when the two scans come from different machines with unrelated coordinate origins); an implausibly large rotation (>20°) is logged as a warning but does not block the job. `infer/segment` picks up `transform_path` from here automatically (see `reference_scan` in the `slice_number` row above) — you don't need to pass it through manually.

### `GET /api/jobs/query_job`
| Arg | Required | Type | Description |
|---|---|---|---|
| `id` | yes | string | RQ job id returned by an `infer/spine` or `infer/segment` call. |

Returns `{"job-ID": ..., "status": <str of RQ result type>, "result": <return value or exception string>}`. Raises if the job id doesn't exist yet/anymore (RQ result TTL applies).

### `GET /api/jobs/get_failed_jobs`
| Arg | Required | Type | Description |
|---|---|---|---|
| `project` | no | string | If given, only returns failures whose job args' `project` field matches. |

**Limitation:** only checks the `high` queue, i.e. spine-labelling failures — failed segmentation jobs (queued on `default`) won't show up here. Use the [RQ Dashboard](#rq-dashboard) to see failures on every queue.

### `POST /api/jobs/submit_jobs_from_csv`
Submits a batch of spine/segment jobs from one uploaded CSV. `multipart/form-data`, not JSON.

| Field | Required | Description |
|---|---|---|
| `project` | yes | Project name applied to every row, unless a row has its own `project` column. |
| `file` | yes | CSV, one row per scan. Required column: `input_path`. Optional column: `job_type` — `spine`, `segment`, or `full` (default `full`: spine job followed by a dependent segment job, same as the two-step pipeline above). Any other column is passed through as an extra argument for that row, using the same names as `infer/spine`/`infer/segment` above (e.g. `vertebra`, `num_slices`, `patient_id`). |

**Response:** `{"message": ..., "jobs": [{"row": <int>, "input_path": ..., "spine_job_id": ..., "segment_job_id": ...}, ...]}` — one entry per CSV row (job ids omitted per-row depending on `job_type`). The row-level `job-ID`s can be polled the same way as any other job via `GET /api/jobs/query_job`.

---

## Conquest (DICOM ingestion) — `/api/conquest`

### `POST /api/conquest/handle_trigger`
Not meant to be called directly — this is invoked automatically by the Conquest DICOM server's Lua trigger script ([conquest/trigger.lua](../conquest/trigger.lua)) whenever a new DICOM object is received on the built-in PACS listener.

| Arg (query string) | Required | Description |
|---|---|---|
| `series_uid` | yes | DICOM SeriesInstanceUID of the received object. |
| `study_uid` | yes | DICOM StudyInstanceUID. |
| `patient_id` | yes | DICOM PatientID. |
| `modality` | yes | DICOM Modality — handled values: `CT`, `CBCT` (inferred when `modality=="CT"` and `manufacturer` is Elekta), `RTSTRUCT`. `RTPLAN`/`RTDOSE` are explicitly rejected (raises); anything else raises "can't handle modality."|
| `manufacturer` | yes | DICOM Manufacturer — used only to detect the CT→CBCT special case above. |

Behavior by modality:
- **CT**: files matching the request's header tags are moved from the Conquest inbox into `/data/inbox/<patient_id>/<study_uid>/<series_uid>/<modality>/`, then a spine job is submitted followed by a dependent segment job (`num_slices=1`, project `"Unassigned"`). No DICOM header field is reliable enough to auto-route scans to the correct real project (Study Description isn't consistently populated, and there's no site-specific AE-title/port routing), so everything lands in the `Unassigned` project and a human assigns it to the right project afterward via [`POST /api/database/reassign_patient`](#post-apidatabasereassign_patient) or [`POST /api/database/assign_patients_from_csv`](#post-apidatabaseassign_patients_from_csv) (surfaced in the frontend as "Assign to Project").
- **CBCT**: looks up an existing labelled planning CT for the same `patient_id` in the `spine` Mongo collection; raises if none is found. Submits one `infer/register` job to align the CBCT onto that planning CT (see [`POST /api/jobs/infer/register`](#post-apijobsinferregister)), then one segment job per vertebral level the planning CT was labelled at (that also has a CBCT model), each depending on the registration job (`depends_on`) and with `resample=True`, `reference_scan=<planning CT id>`, `calibrate_cbct=True`, `calibration_structure="brainstem"` hardcoded — no `slice_number` is set explicitly; it's still the planning CT's own recorded slice number for that level, which only becomes valid for the CBCT once the registration job's transform has been used to resample it onto the planning CT's grid (see the `infer/segment` `slice_number` row above).
- **RTSTRUCT**: links the struct file path to the matching planning CT's `images` Mongo entry (matched by `study_uid`, or by parsing the RTSTRUCT's `ReferencedFrameOfReferenceSequence` if no match is found by study).
- **RTPLAN / RTDOSE**: always raises (rejected).

---

## Database — `/api/database`

### `POST /api/database/delete_entry`
Body: `{"_id": <string, required>, "collection": <string, required>}`. Deletes one document by `_id` from the named Mongo collection (`images`, `spine`, `segmentation`, `quality_control`, `weights`, etc. — not validated against a whitelist, so a typo'd collection name just deletes nothing silently).

### `GET /api/database/get_qc_report`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |
| `_id` | no | If given, restrict to one series' QC report. |

Returns non-empty `qc_report` entries (the free-text/structured fail reports submitted via `fail_qa_report`) as a list of `(series_uuid, qc_report)` tuples.

### `GET /api/database/get_project_info`
No args. Returns `[{"name": <project>, "num_patients": <int>, "num_images": <int>}, ...]` for every project.

### `GET /api/database/get_patients_in_project`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |

Returns `[{"patient_id": ..., "series_uuids": [...]}, ...]`.

### `GET /api/database/get_levels_to_QA`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |

Returns the set of unique vertebral levels that have **any** segmentation result recorded for the project. Despite the name, this does not filter by QA status — it's really "which levels exist in this project," used by the frontend to build the QA navigation menu.

### `GET /api/database/get_patient_filter_options`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |
| `patient_id` | yes | Patient id. |

Returns `{"data": [{"vertebra": ..., "compartment": ..., "modality": ..., "acquisition_date": ...}, ...]}` — every (vertebra, compartment, modality) combination this specific patient actually has completed segmentation data for, deduplicated (one entry per combo, tagged with the most recent acquisition date seen for it). Compartment options are read strictly from the literal keys stored in `statistics` — this deliberately does **not** reuse the "offer IMAT whenever skeletal_muscle is present" heuristic used elsewhere (e.g. `patientQA.py`), since that heuristic doesn't check modality and can offer IMAT as an option even where it was never actually computed (e.g. CBCT). Used by the frontend to build dynamic filter dropdowns instead of a hardcoded vertebra/compartment list.

### `GET /api/database/get_labelling_status`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |
| `level` | no | If given, also checks whether that specific vertebral level was found by spine labelling (not just whether labelling ran at all). |

Side effect: writes a CSV to `/data/outputs/labelling_status_<project>.csv` (or `..._<level>_<project>.csv`) with per-series pass/fail. The JSON response only returns the aggregate `% passed` — read the CSV for the per-patient breakdown.

### `GET /api/database/get_segmentation_status`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |

Same pattern as `get_labelling_status` but for `segmentation_done`; writes `/data/outputs/segmentation_status_<project>.csv`. No `level` filter supported.

### `GET /api/database/get_input_args`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |
| `_id` | effectively yes (default `None`, which won't match anything) | Series id. |

Returns the raw `images` collection document for that series (i.e. every parameter recorded for the original job request).

### `GET /api/database/get_spine_entry`
| Arg | Required | Description |
|---|---|---|
| `project` | yes | Project name. |
| `_id` | effectively yes | Series id. |

Returns the raw `spine` collection document (vertebra predictions + all parameters used).

### `POST /api/database/extract_stats_from_mask`
Enqueues (queue `default`) a job that re-computes area/density statistics from a **manually supplied or manually edited** mask file, without re-running model inference. Used by the manual-edit workflow (see [examples/python/add_edited_masks_to_db.py](../examples/python/add_edited_masks_to_db.py)).

| Arg | Required | Type | Default | Description |
|---|---|---|---|---|
| `_id` | yes | string | — | Series id; must already have a `segmentation` entry in Mongo. |
| `mask_path` | yes | string | — | Path (container-visible) to the `.nii.gz` mask to extract stats from. |
| `project` | yes | string | — | Project name. |
| `vertebra` | yes | string | — | Vertebral level this mask corresponds to. |
| `compartment` | yes | string | — | Tissue compartment the mask represents. |
| `input_path` | no | string | existing `segmentation.input_path` for this `_id` | Path to the original scan. |
| `output_dir` | no | string | existing `segmentation.output_dir` for this `_id` | Where to write updated outputs. |
| `is_edit` | no | string bool | `True` | `True` = mask is an edited version of a model output (stored under DB key `<vertebra>-edited`); `False` = manually generated from scratch (stored under `<vertebra>-manual`). |
| `dilate_mask` | no | string bool | not dilated | Whether to morphologically dilate the mask before extracting stats. |
| `worldmatch_correction` | no | string bool | `False` | Same meaning as elsewhere. |
| `generate_bone_mask` | no | string bool / path | `True` | Same meaning as elsewhere. |
| `slice_number` | no | int / numeric string | looked up from `spine` collection via `_id` + `vertebra` | Same meaning as elsewhere. |
| `modality` | no | string | `"CT"` | Same meaning as elsewhere. |
| `muscle_threshold` / `fat_threshold` | no | string tuple | engine defaults | Same meaning as elsewhere. |

### `POST /api/database/change_project`
Body: `{"_id": <string, required>, "current_project": <string, required>, "new_project": <string, required>}`. Reassigns the `project` field across the `images`, `segmentation`, `spine`, and `quality_control` collections, moves the corresponding output directory on disk, and rewrites stored sanity-image paths. Pass `"_id": "*"` to move **every** document in `current_project` to `new_project` in one call — there is no dry-run/confirmation step, so this is effectively irreversible without manually reversing it.

### `POST /api/database/change_patient_id`
Body: `{"_id": <string, required>, "current_patient_id": <string, required>, "new_patient_id": <string, required>}`. Renames the patient id on all records for the given series `_id` and moves the output directory accordingly. **Note:** `current_patient_id` is required in the request but not actually checked against the existing value — only `_id` and `new_patient_id` matter, so a wrong `current_patient_id` won't be caught.

### `GET /api/database/find_patient`
| Arg | Required | Description |
|---|---|---|
| `patient_id` | yes | Patient id to search for. |

Cross-project lookup — deliberately **not** scoped to a single project, since it exists to find data sitting in the `Unassigned` project (or already split across others) before reassigning it. Returns `{"message": ..., "patient_id": ..., "projects": [{"project": <name>, "series": [{"_id", "series_uuid", "modality", "acquisition_date"}, ...]}, ...]}` — one entry per project this patient currently has data in. Empty `projects` list (still `200`) if nothing is found.

### `POST /api/database/reassign_patient`
Body: `{"patient_id": <string, required>, "current_project": <string, required>, "new_project": <string, required>}`. Moves every series belonging to `patient_id` within `current_project` into `new_project` — the patient-level counterpart to `change_project` (which only supports "one series by `_id`" or "every document in a project"). Project names are validated server-side (`^[A-Za-z0-9_-]+$`). Before moving anything, checks the `high`/`default`/`low` RQ queues (queued **and** running jobs) for any job whose args reference this `patient_id`; if found, returns `409` with `{"message": ..., "skipped": true}` instead of reassigning, since a spine/segment job still in flight recomputes its own `output_dir` from the request captured at enqueue time and would otherwise silently resurrect the old project's directory after the move. On success, returns `{"message": ..., "series_uuids": [...]}`.

### `POST /api/database/assign_patients_from_csv`
Bulk version of `reassign_patient` from an uploaded CSV. `multipart/form-data`, not JSON.

| Form field | Required | Description |
|---|---|---|
| `file` | yes | CSV, one row per patient. Required column: `patient_id`. Optional per-row columns `current_project`/`new_project` override the form-level defaults below. |
| `current_project` | no | Default project to move rows **from**. Defaults to `Unassigned`. |
| `new_project` | conditionally | Default project to move rows **to** — required unless every row supplies its own `new_project` column. |

Same in-flight-job guard and project-name validation as `reassign_patient`, applied per row. Errors on one row (missing `patient_id`, invalid project name, in-flight job, or no matching data) don't abort the batch — response is `{"message": ..., "results": [{"row": <int>, "patient_id": ..., "moved_series": [...], "new_project": ...} or {"row": <int>, "patient_id": ..., "error": <string>}, ...]}`.

### `POST /api/database/upload_sanity_to_web`
**Not implemented** — the handler body is a bare `...` placeholder. It reads a JSON body but performs no action and has no `return`, so calling it will error (Flask requires a response).

---

## Post-processing — `/api/post_process`

### `POST /api/post_process/get_rt_struct`
Body: `{"_id": <string, required>, "project": <string, required>, "for_editing": <string, required — must be exactly `"True"` to enable, anything else is treated as false>}`. Combines every `*.nii.gz` mask in the segmentation's `output_dir/masks/` into a single RTSTRUCT DICOM referencing the original scan series, and saves it either alongside the masks (`for_editing` false) or into `/data/outputs/<project>/masks_to_edit/<patient_id>/<_id>/` together with a copy of the original scan (`for_editing` true, for use in external editing tools). Returns `{"output_path": ...}`.

### `POST /api/post_process/get_stats_for_series`
Body: `{"_id": <string, required>, "project": <string, required>, "format": <string, optional, "voxels" (default) | "metric">}`.
**Note:** `vertebra` is hardcoded to `"L3"` inside the handler (marked `#TODO This should be a variable` in the code) — it always returns L3 stats regardless of what other levels exist for the series. The `"metric"` format branch fetches per-image pixel spacing but never actually converts the area values with it, so in practice `"metric"` currently behaves identically to `"voxels"`.

### `GET /api/post_process/get_stats_for_project_v2` and `GET /api/post_process/get_stats_for_project`
| Arg | Required | Type | Description |
|---|---|---|---|
| `project` | yes | string | Project name. |
| `download` | no | string, must be exactly `"True"` to enable | If true, streams the resulting CSV back as a file attachment (`<project>_statistics.csv`) instead of returning JSON. |

Both write a per-(patient, vertebra, compartment, slice) CSV to `<OUTPUT_DIR>/<project>/statistics.csv`, including QC pass/fail flags and manual-edit markers. **`v2` is the current version** (per-vertebra `quality_control` schema); the non-`v2` endpoint is kept for backward compatibility with an older, flatter database schema and has extra fallback parsing branches for it. Prefer `v2` for new integrations. Series with no `quality_control` entry at all are silently skipped by both (not just series that failed QC).

### `POST /api/post_process/export_segmentations`
Body: `{"_id": <string, required>, "project": <string, required>, "compartment": <string, required — one of `total_muscle`, `skeletal_muscle`, `visceral_fat`, `subcutaneous_fat`, `IMAT`, `bone`>, "output_dir_name": <string, required>}`. Copies the requested compartment mask (for `total_muscle`, combines the `skeletal_muscle` + `IMAT` masks) plus a copy of the original scan into `/data/outputs/<project>/<output_dir_name>/<patient_id>/<_id>/SCAN`, for use with external mask-editing tools.

### `GET /api/post_process/get_stats_for_patient`
| Arg | Required | Type | Description |
|---|---|---|---|
| `project` | yes | string | Project name. |
| `patient_id` | yes | string | Patient id. |
| `vertebra` | yes | string | Vertebral level to report on. |
| `compartment` | yes | string | Tissue compartment to report on. |
| `modality` | no | string | If given, only include series whose `images.modality` matches. |

Returns a longitudinal series across the patient's scans in the project for this (vertebra, compartment[, modality]) combination: `{"data": [{"date": ..., "series_uuid": ..., "area": <cm²>, "density": <HU>, "area_pct_change": ..., "density_pct_change": ..., "qc_status": 1|2}, ...]}`, sorted by date, with area converted from voxels to cm² using pixel spacing, both absolute values **and** % change relative to the earliest (baseline) scan returned, and `series_uuid`/`qc_status` included per point. **Failed-QC series (`overall_qc_state.<vertebra> == 0`) are excluded before the baseline is chosen**, not just before display — so a failed scan can never corrupt every later point's % change even if it happened to be the earliest scan (`qc_status` in the response is therefore always `1` (pass) or `2` (todo), never `0`). Returns HTTP 500 if no matching (non-failed) series exist.

### `GET /api/post_process/get_population_stats`
| Arg | Required | Type | Description |
|---|---|---|---|
| `project` | yes | string | Project name. |
| `vertebra` | yes | string | Vertebral level. |
| `compartment` | yes | string | Tissue compartment. |
| `modality` | no | string | If given, only include series whose `images.modality` matches. |

Returns `{"data": [{"patient_id": ..., "date": ..., "area": <cm²>, "density": <HU>}, ...]}` — one row per matching series **across every patient in the project** at this (vertebra, compartment[, modality]) combination, used to plot the project-wide distribution a single patient's own measurements can be compared against. Same QC-exclusion rule as `get_stats_for_patient` (failed series are dropped, not just hidden), so the population isn't skewed by bad segmentations either.

### `POST /api/post_process/generate_report`
Body: `{"project": <string, required>, "patient_id": <string, required>, "combos": [{"vertebra": ..., "compartment": ..., "modality": ...}, ...] (required, non-empty)}`.

Generates a PDF body-composition report for clinical review and returns it as a file download (`mimetype: application/pdf`). For each requested combo, fetches its trend series via the same shared logic (and QC-exclusion rule) as `get_stats_for_patient`, and renders one longitudinal chart (matplotlib, light background regardless of the caller's UI theme). Also includes a weight-history table (from the `weights` collection) and a grid of exemplar QA images — one per ~7-day window across the patient's scans, sourced from `quality_control.paths_to_sanity_images['ALL']` for the **first** combo's vertebra (v1 scope: exemplar images cover only the first requested combo's vertebra, not every selected vertebra). Written to `<OUTPUT_DIR>/<project>/<patient_id>/reports/<patient_id>_report_<timestamp>.pdf` (not deleted afterward, matching the CSV-export endpoints' persist-for-reuse convention).

---

## Sanity QA (legacy, per-vertebra) — `/api/sanity`

This blueprint is the **older** QA workflow: one pass/fail/todo status per vertebral level (`2`=to-do, `1`=pass, `0`=fail) at `quality_control.<vertebra>`. A newer, per-compartment workflow runs in parallel — see [`/api/patient_qa`](#patient-qa-per-compartment--apipatient_qa) — which tracks status per tissue compartment plus an aggregate `overall_qc_state.<vertebra>`. Both read/write the same `quality_control` collection, and `GET /api/sanity/get_summary` reads the *newer* `overall_qc_state` field, so pick whichever blueprint matches the granularity you need rather than assuming they're independent.

### `POST /api/sanity/fetch_first_image`
| Arg (query string) | Required | Description |
|---|---|---|
| `project` | yes | Project name. |
| `vertebra` | yes | Vertebral level. |

Picks a random still-to-do (`2`) image for the project+vertebra; if none, falls back to a fail (`0`), then to a pass (`1`). Returns the sanity-check image as base64 PNG plus its DB status. If genuinely nothing exists for that project+vertebra, returns `400`.

### `POST /api/sanity/fetch_image_by_id`
Query: `_id` (yes), `project` (yes), `vertebra` (yes). Returns one specific sanity image, with `status` combining `quality_control.SPINE` and `quality_control.<vertebra>` — a fail on either counts as a fail overall.

### `GET /api/sanity/fetch_patient_list`
Query: `project` (yes), `vertebra` (yes). Returns `{"image_dict": {patient_id: [series_id, ...]}}` for every series that has a QC entry for this vertebra, ordered to surface to-do items first.

### `POST /api/sanity/fetch_image_list`
Query: `project` (yes), `vertebra` (yes). Returns `{"id_list": [...]}` — a shuffled flat list of series ids with a QC entry for this vertebra (to-do first if any exist).

### `POST /api/sanity/fetch_spine_by_id`
Query: `_id` (yes), `project` (yes), `vertebra` (yes, used only when the stored spine sanity image is keyed per-level). Returns the base64 spine-labelling QA image. If `_id`'s own `quality_control` entry has no `SPINE` image (e.g. a CBCT, which never runs `infer/spine` itself), falls back to the `SPINE` image of the reference scan recorded in the `registration` collection (see [`POST /api/jobs/infer/register`](#post-apijobsinferregister)), if one exists. Returns `404` if no spine image can be found either way.

### `POST /api/sanity/fetch_registration_by_id`
Query: `_id` (yes), `project` (yes), `vertebra` (yes). Returns the base64 registration QC overlay image (planning CT slice | registered moving-scan slice) written by an `infer/register` job (see [`POST /api/jobs/infer/register`](#post-apijobsinferregister)), read from the `registration` collection (not `quality_control`). Returns `404` if this scan has no registration record for the given vertebra — expected for any scan that didn't reuse another scan's spine labelling (e.g. a planning CT itself).

### `POST /api/sanity/pass_qa`
Query: `project` (yes), `_id` (yes), `vertebra` (yes). Sets **both** `quality_control.<vertebra>` and `quality_control.SPINE` to `1` (pass) — passing a compartment implies its spine labelling is also being confirmed correct.

### `POST /api/sanity/fail_qa`
Query: `project` (yes), `_id` (yes), `vertebra` (yes), `mode` (yes — one of `segmentation`, `labelling`, `both`; any other value returns HTTP 400). Sets the relevant flag(s) to `0` (fail), the other to `1` (pass) unless `mode="both"`.

### `GET /api/sanity/get_summary`
Query: `project` (yes), `vertebra` (yes). Returns `{"pass": n, "fail": n, "todo": n, "total": n}` counts, computed from `overall_qc_state.<vertebra>` (the field written by the newer per-compartment workflow — see the blueprint-level note above).

### `POST /api/sanity/fail_qa_report`
Query: `project` (yes), `_id` (yes), `vertebra` (yes). Body: free-form JSON object; must include `failMode` (one of `badSegmentation` | `wrongLevel` | anything else, treated as "fail both spine and segmentation"). Other body keys are stored verbatim as the QC report (keys with an empty-string value are dropped before storing). Also updates the pass/fail flags per the `failMode` logic (same semantics as `fail_qa`'s `mode`).

---

## Patient QA (per-compartment) — `/api/patient_qa`

The newer QA workflow: statuses are tracked per compartment (`quality_control.<vertebra>.<compartment>`) with an aggregate `overall_qc_state.<vertebra>` (`2`=to-do, `1`=pass, `0`=fail) used for list views.

### `GET /api/patient_qa/fetch_patient_list`
Query: `project` (yes), `vertebra` (yes). Returns `{"image_dict": {patient_id: {series_id: acquisition_date, ...}}}` for series with an `overall_qc_state.<vertebra>` entry, to-do surfaced first.

### `GET /api/patient_qa/get_filtered_patient_list`
Query: `project` (yes), `vertebra` (yes). Returns `{"status_dict": {"to-do": [patient_id, ...], "failed": [...], "passed": [...]}}` — one bucket per patient id, aggregated across all their series with a "todo beats fail beats pass" priority when a patient has multiple series in different states.

### `GET /api/patient_qa/fetch_image_by_id`
Query: `_id` (yes), `project` (yes), `vertebra` (yes). Like the sanity blueprint's version, but additionally returns `compartments`: the list of tissue compartments the model bank says *should* have been segmented for this vertebra/modality (plus `IMAT` appended if `skeletal_muscle` is one of them) — used by the frontend to render the correct set of per-compartment pass/fail toggles.

### `POST /api/patient_qa/pass_qa`
Query: `project` (yes), `_id` (yes), `vertebra` (yes). Sets every compartment currently recorded under `quality_control.<vertebra>` to `1`, and `overall_qc_state.<vertebra>` to `1`.

### `POST /api/patient_qa/fail_qa_report`
Query: `project` (yes), `_id` (yes), `vertebra` (yes). Body: JSON, must include `failMode` (`badSegmentation` | `wrongLevel` | other). If `failMode == "badSegmentation"`, must also include `failedCompartments` (list of compartment name strings) — those compartments are set to `0`, all others under that vertebra to `1`. `wrongLevel` fails only the `SPINE` field. Anything else fails every compartment. `overall_qc_state.<vertebra>` is set to `0` in all three cases.

### `GET /api/patient_qa/get_image_pass_rate`
Query: `project` (yes), `vertebra` (yes). Returns `{"passed": n, "total": n, "pass_rate": <float, rounded to 1dp>}` based on `overall_qc_state.<vertebra> == 1`.

---

## Weights — `/api/weights`

Manual patient body-weight tracking (independent of image segmentation), keyed by `patient_id` as the Mongo `_id` in the `weights` collection.

### `POST /api/weights/post_weight`
Query: `patient_id` (yes), `weight` (yes, stored as-supplied, cast to `float` only when read back), `date` (yes, stored as the dict key — must be a string that sorts correctly, e.g. ISO `YYYY-MM-DD`; not validated). Upserts one measurement.

### `GET /api/weights/fetch_weights`
Query: `_id` (yes — the patient id). Returns `{"data": [(date, weight, pct_change_from_baseline), ...]}` sorted by date ascending; empty list if no entry/no measurements exist.

### `POST /api/weights/delete_weight`
Query: `_id` (yes — patient id), `date` (yes). Removes that date's entry. Returns a generic `500` if the patient has no `weights` document, or if `date` isn't one of its existing keys.

---

## RQ Dashboard

Mounted at `/rq-dashboard` (no API args) — a browser UI for inspecting the Redis/RQ job queues (`high`, `default`, `low`) directly: queued/running/failed/finished jobs, retry, etc. Useful for debugging stuck or failed inference jobs alongside `GET /api/jobs/get_failed_jobs`.
