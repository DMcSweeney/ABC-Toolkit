curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "current_patient_id": "my_patient", "new_patient_id": "their_new_id"}'\
    https://localhost:5001/api/database/change_patient_id