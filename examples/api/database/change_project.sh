curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"_id": "*", "current_project": "inbox", "new_project": "mosaiqExportTest"}'\
    http://localhost:5001/api/database/change_project