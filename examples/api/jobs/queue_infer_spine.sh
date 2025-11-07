curl -X POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"input_path": "/data/inputs/test_patient", "patient_id": "test_patient", "project": "hello"}'\
    https://localhost:5001/api/jobs/infer/spine