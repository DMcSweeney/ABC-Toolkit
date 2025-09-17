curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"_id": "1.3.6.1.4.1.5962.99.1.2540809840.907079848.1673283120752.11180.0", "current_patient_id": "STAMPEDE", "new_patient_id": "1074"}'\
    http://localhost:5001/api/database/change_patient_id