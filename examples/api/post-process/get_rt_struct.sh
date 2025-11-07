curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "project": "hello", "for_editing": "True"}'\
    https://localhost:5001/api/post_process/get_rt_struct