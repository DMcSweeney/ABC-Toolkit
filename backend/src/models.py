"""
Schema for the database
"""
from sqlalchemy import ForeignKey, Column, String
from sqlalchemy.orm import relationship

from app import db

LEVELS = ["C1","C2","C3", "C4", "C5", "C6", "C7", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9",
                    "T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5", "Sacrum", "Thigh"]

COMPARTMENTS = ["skeletal_muscle", "subcutaneous_fat", "visceral_fat", "IMAT", "body"]


class Users(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=True)


class Images(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    patientID = db.Column(db.String, nullable=False)
    project = db.Column(db.String, nullable=False)
    path = db.Column(db.String, nullable=False)
    series_uuid = db.Column(db.String, nullable=False)

class Results(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, ForeignKey(Images.id), primary_key=True)
    patientID = db.Column(db.String, nullable=False)
    relationship('Images', foreign_keys='Results.id')

## Iteratively add columns for every level
for compartment in COMPARTMENTS:
    for level in LEVELS:
        setattr(Results, f'{level}_{compartment}_area', Column(String)) ##String since values will be stored in a dict. to handle multi-slice results.
        setattr(Results, f'{level}_{compartment}_density', Column(String))


db.drop_all()
db.create_all()
db.session.commit()