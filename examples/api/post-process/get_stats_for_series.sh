curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "project": "hello", "format": "metric"}'\
    https://localhost:5001/api/post_process/get_stats_for_series