"""
Shared constants referenced across API blueprints.
"""

# Project every Orthanc-ingested scan lands in until a human assigns it to a
# real project via /api/database/reassign_patient or /assign_patients_from_csv.
UNASSIGNED_PROJECT = "Unassigned"
