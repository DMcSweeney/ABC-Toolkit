"""
Example script for submitting jobs to the toolkit
"""
import os
import requests
import polars as pl

## ABC config
host_ip = 'localhost'
spine_url = f'https://{host_ip}:5001/api/jobs/infer/spine'
segment_url = f'https://{host_ip}:5001/api/jobs/infer/segment'

## DATA config
input_dir = "/data/data_for_my_first_project/"
project = 'my_first_project'

def main():
    contents = []

    ## Create all the requests.
    ## This example assumes you have one image per patient and each patient is a folder in input_dir
    for patient in os.listdir(input_dir):
        ## THIS changes depending on how you have defined INPUT_DIR in your .env file
        ## The path provided in the request needs to be the path as seen inside the toolkit (i.e. always starts with /data/inputs/)
        path_in_abc = input_dir.replace('/data/data_for_my_first_project/', '/data/inputs/')
        patient_path = os.path.join(path_in_abc, patient)
        
        ## Create request bodies
        ## You can add other arguments here as needed - see docs for details
        ## In this example, we submit a spine labelling job followed by a segmentation job for L3 +/- 1 slice (i.e. 3 slices in total)
        spine_body = {"input_path": patient_path, "project": project, "patient_id": patient}
        segment_body = {"input_path": patient_path, "project": project, "patient_id": patient, "vertebra": 'L3', "num_slices": "1"}
        data = {'spine': spine_body, 'segment': segment_body}
        contents.append(data)

    ## Submit jobs
    for x in contents:
        print(f'Request: {x}')
        # Submit spine labelling job
        res = requests.post(spine_url, json=x['spine'], verify=False)
        x['segment']['depends_on'] = res.json()['job-ID'] ## Update segment job with the job id
        res = requests.post(segment_url, json=x['segment'], verify=False) ## Submit segment job

if __name__ == '__main__':
    main()
