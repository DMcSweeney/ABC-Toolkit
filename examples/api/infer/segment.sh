curl --request POST\
	--insecure\
	 --header "Content-Type: application/json"\
	 --data '{"input_path": "/data/inputs/some_scan", "project": "hello", "slice_number": "23", "vertebra": "L3", "num_slices": "1"}'\
    https://localhost:5001/api/jobs/infer/segment
