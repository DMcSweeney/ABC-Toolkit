curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "project": "hello", "patient_id": "my_patientID"}'\
    https://localhost:5001/api/database/upload_sanity_to_web