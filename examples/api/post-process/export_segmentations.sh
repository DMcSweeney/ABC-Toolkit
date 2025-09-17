curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"_id": "1.3.6.1.4.1.5962.99.1.963632969.874173844.1671705943881.19200.0", "project": "testingBaselineCTs", "compartment": "total_muscle", "output_dir_name": "masks_to_edit_again"}'\
    http://localhost:5001/api/post_process/export_segmentations
