import os


class BaseConfig():
    DEBUG = os.environ['FLASK_DEBUG']
    SECRET_KEY = 'secret'
    MONGO_URI = f"mongodb://{os.environ['MONGO_INITDB_ROOT_USERNAME']}:{os.environ['MONGO_INITDB_ROOT_PASSWORD']}@mongo:27017/{os.environ['MONGO_INITDB_DATABASE']}?authSource=admin"