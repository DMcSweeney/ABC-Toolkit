curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"_id": "A0164-250646-CBCT-Fx17", "project": "HnN_changes_CBCT", "patient_id": "A0164"}'\
    http://localhost:5001/api/database/upload_sanity_to_web