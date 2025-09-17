### Basic
curl -X POST\
    --header "Content-Type: application/json"\
    --data '{"input_path": "/data/inputs/1053", "patient_id": "1053", "project": "testing", "vertebra": "L3", "num_slices": "1"}'\
    http://10.127.3.25:5001/api/jobs/infer/segment


### MRI
# curl -X POST\
#     --header "Content-Type: application/json"\
#     --data '{"input_path": "/data/inputs/prostateMR_radiomics/patientData/SABR_noADT/3153/MR1", 
#     "project": "mrTest", "vertebra": "Sacrum", "generate_bone_mask": "False",
#     "modality": "MR", "slice_number": 278, "num_slices": 1, "muscle_threshold": "(None, None)", "fat_threshold": "(None, None)"}'\
#     http://localhost:5001/api/jobs/infer/segment

### VIA CONQUEST
# curl -X POST\
#     --header "Content-Type: application/json"\
#     --data '{"input_path": "/data/inputs/ABC-Toolkit/816917893", "project": "inbox", "num_slices": 1}'\
#     http://localhost:5001/api/jobs/infer/segment


## Head and Neck planning CT - with worldmatch correction
# curl -X POST\
#     --header "Content-Type: application/json"\
#     --data '{"input_path": "/data/inputs/sarcopeniaProjects/HnN_CBCT/data/154832774/CT/154832774.nii", "project": "cbct_Testing", "num_slices": 1, 
#     "patient_id": "154832774", "series_uuid": "154832774_pCT", "vertebra": "C3", "worldmatch_correction": "True"}'\
#     http://localhost:5001/api/jobs/infer/segment


### Head and Neck CBCT
# curl -X POST\
#     --header "Content-Type: application/json"\
#     --data '{"input_path": "/data/inputs/sarcopeniaProjects/HnN_CBCT/data/155054082/CBCT/15.02.2017/155054082_ready.nii", "project": "cbct_Testing", "num_slices": 1, 
#     "patient_id": "155054082", "series_uuid": "155054082_CBCT", "vertebra": "C3", "worldmatch_correction": "True", "modality": "CBCT", "slice_number": 76}'\
#     http://localhost:5001/api/jobs/infer/segment