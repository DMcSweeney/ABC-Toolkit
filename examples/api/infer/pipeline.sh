curl --request POST\
	--insecure\
	 --header "Content-Type: application/json"\
	 --data '{"input_path": "/data/inputs/some_scan", "project": "hello"}'\
    https://localhost:5001/api/infer/spine

