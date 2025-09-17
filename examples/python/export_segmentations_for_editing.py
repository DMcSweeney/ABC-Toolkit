"""
Script for reading CSV with _ids to resegment and make calls to /api/post_process/export_segmentations for editing.
"""

import os
import polars as pl
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

retry_strategy = Retry(
  total=3,
  backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)


## ABC config
host_ip = 'localhost' ## DANTE
url = f'http://{host_ip}:5001/api/post_process/export_segmentations'

project = 'testingBaselineCTs'


# with open('./outputs/export_errors_copy.txt', 'r') as f:
#     lines = f.readlines()
#     lines = [line.rstrip() for line in lines]

path_to_csv = './manual_segmentation_list_round2.csv'
df = pl.read_csv(path_to_csv, infer_schema_length=0)
print(df)

output_dir = f'/home/donal/web-abc/data/outputs/{project}/masks_to_edit_again/'

series_to_skip = []
for pat in os.listdir(output_dir):
    series = os.listdir(os.path.join(output_dir, pat))[0]
    scan_path = os.path.join(output_dir, pat, series, 'SCAN')
    if os.path.isdir(scan_path):
        #series_to_skip.append(series)
    
        if len(os.listdir(scan_path)) != 0:
            series_to_skip.append(series) 

print(f'Skipping {len(series_to_skip)} paths')

def main():
    errors = []
    for row in df.rows():
        print(row)
        #series_uuid = row
        trialno, series_uuid = row
        if series_uuid in series_to_skip:
            continue

        payload = {"_id": series_uuid, "project": project, "compartment": "total_muscle", "output_dir_name": "masks_to_edit_again"}
        response = http.post(url, json=payload)
        print(response.status_code)
        if response.status_code != 200:
            errors.append(series_uuid)
    
    print(f'{len(errors)} errors')
    with open('./outputs/export_errors.txt', 'w') as f:
        for line in errors:
            f.write(f'{line}\n')



if __name__ == '__main__':
    main()