curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"_id": "1.3.6.1.4.1.5962.99.1.717926696.1892113523.1671460237608.10363.0", "project": "testEdits", "compartment": "total_muscle", "dilate_mask": "True", "vertebra": "L3", "mask_path": "/data/inputs/manual_edits/1.3.6.1.4.1.5962.99.1.717926696.1892113523.1671460237608.10363.0/TotalMuscle_edited.nii.gz"}'\
    http://localhost:5001/api/database/extract_stats_from_mask