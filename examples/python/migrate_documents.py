"""
Script to re-format documents in an "old" database to the format expected by a new schema 
"""
import os
import SimpleITK as sitk
from pymongo import MongoClient
from datetime import datetime
from database import collections as cl
from tqdm import tqdm

def handle_request(req):
    path_on_host = req['input_path'].replace('/data/inputs/', '/mnt/d/xnat/1.8/archive/')
    ## Handle paramaters and extract info from dicom header if not provided.
    dcm_files = [x for x in os.listdir(path_on_host) if x.endswith('.dcm')]
    if len(dcm_files) == 0:
        raise ValueError
    
    header_keys = {
        #'patient_id': '0010|0020',
        'study_uuid': '0020|000D',
        #'series_uuid': '0020|000e',
        'pixel_spacing': '0028|0030',
        'slice_thickness': '0018|0050',
        'acquisition_date': '0008|0022'
    }
    items = read_dicom_header(os.path.join(path_on_host, dcm_files[0]), header_keys=header_keys)

    ## Add to request
    for key, val in items.items():
        if key in req:
            continue
        if key == 'patient_id' and val == '':
            raise ValueError
        if key == 'series_uuid' and val == None:
            raise ValueError
        
        if key == 'acquisition_date' and val is not None:
            val = datetime.strptime(val, '%Y%m%d').date().strftime('%d-%m-%Y')

        if key == 'pixel_spacing' and "\\" in val:
            val = val.split('\\')
            val = [float(x) for x in val]
            req['X_spacing'] = val[0]
            req['Y_spacing'] = val[1]
            continue

        req[key] = val

    return req

def read_dicom_header(path, header_keys):
    reader = sitk.ImageFileReader()
    reader.LoadPrivateTagsOn()
    reader.SetFileName(path)
    reader.ReadImageInformation()
    metadata = {}
    for k in reader.GetMetaDataKeys():
        v = reader.GetMetaData(k)
        if v == '': #Replace empty string
            v=None
        metadata[k] = v
    data = {}
    for key, val in header_keys.items():
        try:
            data[key] = metadata[val]
        except KeyError:
            data[key] = None # For sql
    return data

def update_collection(database, document, collection, **kwargs):
    if collection == 'images':
        if 'path' not in document:
            ## I.e. it has already been converted to new schema
            return
        params = handle_request(req={'input_path': document['path']})


        update = cl.Images(_id=document['_id'], project=document['project'], patient_id=document['patientID'],
                            series_uuid=document['series_uuid'],
                           labelling_done=document['spine_labelling_done'], **params
                           )

        database.replace_one({'_id': document['_id']}, update.__dict__, upsert=True)

    if collection == 'spine':
        if 'path' not in document:
            ## I.e. it has already been converted to new schema
            return 

        update = cl.Spine(_id=document['_id'], project=document['project'], input_path=document['path'],
            patient_id=document['patientID'], series_uuid=document['series_uuid'],
            prediction=document['prediction'], output_dir=document['path_to_sanity_image'].split('/sanity/')[0],
            all_parameters=document['all_parameters'])
        database.replace_one({'_id': document['_id']}, update.__dict__, upsert=True)

    if collection == 'quality_control':
        if 'patient_id' in document:
            return

        out = kwargs['root_db'].spine.find_one({'_id': document['_id']}, {'output_dir': 1, 'project': 1, 'input_path': 1, 'patient_id': 1,
        'series_uuid':1})
        sanity_images = {'SPINE': os.path.join(out['output_dir'], 'sanity/SPINE.png'), **document['paths_to_sanity_images']}
        qc = {'SPINE': 2, **document['quality_control']}
        update = cl.QualityControl(_id=document['_id'], project=out['project'], input_path=out['input_path'],
            patient_id=out['patient_id'], series_uuid=out['series_uuid'],
            paths_to_sanity_images=sanity_images,
            quality_control=qc)
        database.replace_one({'_id': document['_id']}, update.__dict__, upsert=True)

    if collection == 'segmentation':
        out = kwargs['root_db'].spine.find_one({'_id': document['_id']}, {'output_dir': 1, 'project': 1, 'input_path': 1, 'patient_id': 1,
        'series_uuid':1})
        update = cl.Segmentation(_id=document['_id'], project=out['project'], input_path=out['input_path'],
            patient_id=out['patient_id'], series_uuid=out['series_uuid'],
            output_dir=out['output_dir'], statistics=document['statistics'], all_parameters=document['all_parameters']
            )
        database.replace_one({'_id': document['_id']}, update.__dict__, upsert=True)


def main():
    client = MongoClient("mongodb://abc-user:abc-toolkit@localhost:5002/db?authSource=admin")
    database = client.db

    ## Update images database
    # docs = database.images.find({})
    # for doc in tqdm(docs):
    #     #print(doc)
    #     update_collection(database.images, doc, 'images')
    #     # break

    # Update spine database
    # docs = database.spine.find({})
    # for doc in tqdm(docs):
    #     #print(doc)
    #     update_collection(database.spine, doc, 'spine')
    #     break

    # Update QC database
    # docs = database.quality_control.find({})
    # for doc in tqdm(docs):
    #     print(doc)
    #     update_collection(database.quality_control, doc, 'quality_control', root_db = database)
    #     break

    # Update segmentation database
    docs = database.segmentation.find({})
    for doc in tqdm(docs):
        #print(doc)
        update_collection(database.segmentation, doc, 'segmentation', root_db = database)
        #break


if __name__ == '__main__':
    main()
