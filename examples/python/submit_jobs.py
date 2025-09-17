"""
Example script for submitting jobs to the toolkit
"""
import os
import time
import requests
import polars as pl

## ABC config
host_ip = 'localhost' ## DANTE
spine_url = f'http://{host_ip}:5001/api/jobs/infer/spine'
segment_url = f'http://{host_ip}:5001/api/jobs/infer/segment'

## DATA config
input_dir = "/mnt/f/Filtered"
project = 'VA_scans'

path_to_csv = None #'/mnt/d/BaselineAnalysis/manual_salvage_level_issues.csv'#'/mnt/d/BaselineAnalysis/manual_relabel.csv'
if path_to_csv is not None:
    df = pl.read_csv(path_to_csv, infer_schema_length=0)
    print(df)

def main():
    contents = []

    ## Create all the requests
    for patient in os.listdir(input_dir):

        path_in_abc = input_dir.replace('/mnt/f/', '/data/inputs/')
        #subdirs = os.listdir(os.path.join(input_dir, patient))
        #print(patient, subdirs)
        #assert len(subdirs) == 1, "Too many subdirectories"

        # Find patient in csv
        if path_to_csv is None:
            args = {}
        else:
            args = df.filter(pl.col('patient_id') == patient).to_dict(as_series=False)
            print(args)
            if not args['patient_id'] or args['slice_number'][0] is None:
                continue
            args = {k: v[0] for k, v in args.items() if k in ['patient_id', 'slice_number']}

        patient_path = os.path.join(path_in_abc, patient)

        spine_body = {"input_path": patient_path, "project": project, "patient_id": patient}
        segment_body = {"input_path": patient_path, "project": project, "patient_id": patient, "vertebra": 'L3', "num_slices": "1"}
        data = {'spine': spine_body,
         'segment': segment_body}
        contents.append(data)
        #break

    ## Submit jobs
    for x in contents:
        print(f'Request: {x}')
        # Submit spine labelling job
        res = requests.post(spine_url, json=x['spine'])
        x['segment']['depends_on'] = res.json()['job-ID'] ## Update segment job with the job id 
        res = requests.post(segment_url, json=x['segment']) ## Submit segment job



    # rs = (grequests.post(spine_url, json=x['spine']) for x in contents)    
    # status = grequests.map(rs)
    #print(f'Spine finished in: {time.time() -start}')

    # start=time.time()
    # rs = (requests.post(segment_url, json=x['segment']) for x in contents)  
    # status = grequests.map(rs)
    # print(f'Spine finished in: {time.time() -start}')







if __name__ == '__main__':
    main()
