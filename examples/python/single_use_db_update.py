"""
Minimal script for one-time db updates (e.g. update QC schema) 
"""

from pymongo import MongoClient, UpdateOne, UpdateMany

## Find this in backend/src/config.py
MONGO_URI = f"mongodb://abc-user:abc-toolkit@10.127.3.25:27017/db?authSource=admin"
PROJECT = 'ManualEdits'




def main():

    try:
        print(f'---------- Attempting connection to: {MONGO_URI} ------------')
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=100)
        print('------------ Connected ------------')
    except:
        raise ValueError("Couldn't connect to DB")
    
    database = client.db

    update = {"qc_report": {'L3': {}}, "overall_qc_state": {'L3': 2}} 



    ids = database.quality_control.distinct("_id", {"project": PROJECT})
    operations = []
    for _id in ids:
        cursor = database.quality_control.find_one({"_id": _id, "project": PROJECT})
        compartments = cursor['paths_to_sanity_images'].keys()
        qc = {'L3': {compartment: 2 for compartment in compartments if compartment not in ['ALL', 'body']}}
        update['quality_control'] = qc

        #print(update)
        operations.append(
            UpdateOne(
                {"_id": _id}, {"$set": update}
            
            )) 
    status = database.quality_control.bulk_write(operations, ordered=False)
    print(status)


if __name__ == '__main__':
    main()