"""
Script for uploading edited masks, extracting stats and adding them to the database
"""
import os
import requests


host_ip = 'localhost' ## DANTE
url = f'https://{host_ip}:5001/api/database/extract_stats_from_mask'

## DATA config
input_dir = "./data/inputs/hello" ## Data location on host

## Path mounted to ./data/inputs/ -- usually INPUT_DIR in .env
input_dir_mount= './data/inputs/' 
project = 'hello'

def main():
    contents = []

    ## Create all the requests
    for patient_id in os.listdir(input_dir):
        for series_uuid in os.listdir(os.path.join(input_dir, patient_id)):

            path_in_abc = input_dir.replace(input_dir_mount, '/data/inputs/')

            patient_path = os.path.join(path_in_abc, patient_id, series_uuid)

            mask_path = [os.path.join(patient_path, x) for x in os.listdir(os.path.join(input_dir, patient_id, series_uuid)) if 'edit' in x]
            if not mask_path: continue # Skip if no match

            data = {'_id': series_uuid, "input_path": os.path.join(patient_path, 'SCAN'), "mask_path": mask_path[0], "project": project, "compartment": "total_muscle", "vertebra": "L3", "dilate_mask": "True"}
            contents.append(data)
        #break

    ## Submit jobs
    for x in contents:
        print(f'Request: {x}')
        res = requests.post(url, json=x, verify=False) ## Submit segment job
    


if __name__ == '__main__':
    main()