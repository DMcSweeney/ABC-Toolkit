curl --request POST\
	 --header "Content-Type: application/json"\
	 --data '{"input_path": "/data/inputs/test/timepoint1", "project": "testing"}'\
    http://127.0.0.1:5001/api/infer/spine
