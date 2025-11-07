curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "*", "current_project": "hello", "new_project": "hello_again"}'\
    https://localhost:5001/api/database/change_project