curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "collection": "quality_control"}'\
    https://localhost:5001/api/database/delete_entry