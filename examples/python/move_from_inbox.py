"""
Script for moving patients/images fromn the inbox to a new project specified by NEW_PROJECT
"""
import requests

NEW_PROJECT = 'testing'

DEST_IP = "192.168.117.26"

def main():
    url = 'http://{DEST_IP}:5001/api/database/change_project'
    payload = {"_id": "*", "current_project": "inbox", "new_project": NEW_PROJECT}
    requests.post(url, json=payload)


if __name__ == '__main__':
    main()