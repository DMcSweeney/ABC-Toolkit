curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "project": "hello", "compartment": "total_muscle", "output_dir_name": "hello"}'\
    https://localhost:5001/api/post_process/export_segmentations
