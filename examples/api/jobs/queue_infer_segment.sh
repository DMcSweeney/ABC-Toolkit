### Basic
curl -X POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"input_path": "/data/inputs/test_patient", "patient_id": "test_patient", "project": "hello", "vertebra": "L3", "num_slices": "1"}'\
    https://localhost:5001/api/jobs/infer/segment


### MRI
# curl -X POST\
#      --insecure\
#     --header "Content-Type: application/json"\
#     --data '{"input_path": "/data/inputs/test_MR_scan", 
#     "project": "hello_MRI", "vertebra": "Sacrum", "generate_bone_mask": "False",
#     "modality": "MR", "slice_number": 278, "num_slices": 1, "muscle_threshold": "(None, None)", "fat_threshold": "(None, None)"}'\
#     https://localhost:5001/api/jobs/infer/segment


### Head and Neck cone-beam CT (CBCT)
# curl -X POST\
#     --header "Content-Type: application/json"\
#     --data '{"input_path": "/data/inputs/some_CBCT", "project": "cbct_Testing", "num_slices": 1, 
#     "patient_id": "some_id", "series_uuid": "some_series", "vertebra": "C3", "modality": "CBCT"}'\
#     https://localhost:5001/api/jobs/infer/segment