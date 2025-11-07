curl --request POST\
    --insecure\
    --header "Content-Type: application/json"\
    --data '{"_id": "some_id_in_database", "project": "hello", "compartment": "total_muscle", "dilate_mask": "True", "vertebra": "L3", "mask_path": "/data/inputs/manual_edits/some_id_in_database/TotalMuscle_edited.nii.gz"}'\
    https://localhost:5001/api/database/extract_stats_from_mask