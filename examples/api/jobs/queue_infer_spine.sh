curl -X POST\
    --header "Content-Type: application/json"\
    --data '{"input_path": "/data/inputs/1053", "patient_id": "1053", "project": "testing"}'\
    http://10.127.3.25:5001/api/jobs/infer/spine