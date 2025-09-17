"""
Testing asynchronous requests
"""
import os
import time
import requests
import grequests

spine_url = 'http://localhost:5001/api/jobs/infer/spine'
segment_url = 'http://localhost:5001/api/jobs/infer/segment'

def main():
    input_dir = '/home/donal/ABC-toolkit/web-abc/data/inputs/'
    contents = []
    files = os.listdir(input_dir)
    for file in files:
        spine_body = {"input_path": os.path.join('/data/inputs', file), "project": "testing", "patient_id": file}
        segment_body = {"input_path": os.path.join('/data/inputs', file), "project": "testing", "patient_id": file, "vertebra": 'L3', "num_slices": "1"}

        data = {'spine': spine_body, 'segment': segment_body}
        contents.append(data)
    start=time.time()
    # for x in contents:
    #     print(f'Request: {x}')
    #     res = requests.post(spine_url, json=x['spine'])
    #     res = requests.post(segment_url, json=x['segment'])
    # rs = (grequests.post(spine_url, json=x['spine']) for x in contents)    
    # status = grequests.map(rs)
    # print(f'Spine finished in: {time.time() -start}')

    start=time.time()
    rs = (requests.post(segment_url, json=x['segment']) for x in contents)  
    status = grequests.map(rs)
    print(f'Spine finished in: {time.time() -start}')

if __name__ == '__main__':
    main()

