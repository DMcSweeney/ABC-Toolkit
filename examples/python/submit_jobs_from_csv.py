"""
Example script for submitting jobs to the toolkit.
Accepts input 
"""
import os
import requests
import polars as pl

## TOOL config
host_ip = 'localhost'
spine_url = f'http://{host_ip}:5001/api/jobs/infer/spine'
segment_url = f'http://{host_ip}:5001/api/jobs/infer/segment'

## DATA config
project = 'hello'

## Path mounted to ./data/inputs/ -- usually INPUT_DIR in .env
input_dir_mount= './data/inputs/'

## Path to csv file where columns are arguments passed to requests
path_to_csv = './data/list_of_requests.csv' # None - to ignore
if path_to_csv is not None:
    df = pl.read_csv(path_to_csv)

def main():
    # Holds all requests
    contents = []

    ## Create all the requests by iterating through input directory (assumes patients seperated into different folders)
    for row in df.rows(named=True):
        input_path = row['input_path']

        path_in_tool = input_path.replace(input_dir_mount, '/data/inputs/')
        #patient_path = os.path.join(path_in_tool, patient)

        # Find patient in csv
        if path_to_csv is None:
            args = {}
        #else:
            #args = df.filter(pl.col('patient_id') == patient_id).to_dict(as_series=False)
            #args = {k: v[0] for k, v in args.items()}
        
        spine_body = {
            "project": project, # Project this request belongs to
            "input_path": path_in_tool, # Path to scan 
            # 'series_uuid': series_uuid # Unique identifier for this scan !! If not provided - read from scan header
            **args ## Any additional args provided in CSV
            }
        
        segment_body = {
            "project": project,
            "input_path": path_in_tool, 
            "vertebra": 'L3', # What slice to select & what segmentation model to use. 
            "num_slices": "1", # How many slices either side of the selected slice (i.e if 1, 3 slices are segmented)
            **args  
            }
        data = {'spine': spine_body, 'segment': segment_body}
        contents.append(data)
        #break

    ## Submit jobs
    for x in contents:
        print(f'Request: {x}')
        # Submit spine labelling job
        res = requests.post(spine_url, json=x['spine'])
        x['segment']['depends_on'] = res.json()['job-ID'] ## Update segment job with the job id 
        res = requests.post(segment_url, json=x['segment']) ## Submit segment job







if __name__ == '__main__':
    main()
