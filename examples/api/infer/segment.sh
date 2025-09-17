curl --request POST\
	 --header "Content-Type: application/json"\
	 --data '{"input_path": "/data/inputs/BaselineAnalysis/salvage_scan_issues/16172/Series 008 [CT - Std Volume Vol Body Port Ven]/", "project": "testingBaselineCTs", "slice_number": "414", "vertebra": "L3", "num_slices": "1"}'\
    http://localhost:5001/api/jobs/infer/segment
