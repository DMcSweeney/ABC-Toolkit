curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"input_path": "/data/inputs/Donal/oesophagus_pCT/data/additional_raw/131743923/CT", "project": "totalSeg"}'\
    http://localhost:5001/api/totalsegmentator