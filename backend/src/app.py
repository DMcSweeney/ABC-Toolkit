"""
Main flask application
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler

from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
from redis import Redis
import rq_dashboard

import main
from config import BaseConfig


INPUT_DIR = '/data/inputs/'
OUTPUT_DIR = '/data/outputs/'

logger = logging.getLogger(__name__)

logging.basicConfig(#filename=f'/var/log/backend-.log',
level=logging.INFO,
format="[%(asctime)s] [%(process)s] [%(threadName)s] [%(levelname)s] (%(name)s:%(lineno)d) - %(message)s",
datefmt="%Y-%m-%d %H:%M:%S",
force=True,
)

handler = TimedRotatingFileHandler("/var/log/master_logs", "midnight", 1)
handler.suffix = '%d-%m-%Y_%H-%M'
logger.addHandler(handler)

# Init flask app
app = Flask(__name__, instance_relative_config=True)
app.config.from_object(BaseConfig)
app.config['INPUT_DIR'] = INPUT_DIR
app.config['OUTPUT_DIR'] = OUTPUT_DIR


#Connect to MongoDB
logger.info(f"Starting connection to: {app.config['MONGO_URI']}")
mongo = PyMongo(app)

# Connect to Redis
logger.info(f"Connecting to Redis: redis://redis:6379")
redis = Redis(host="redis", port=6379)

## Connect to RQ dashboard
app.config["RQ_DASHBOARD_REDIS_URL"] = f"redis://redis:6379"
rq_dashboard.web.setup_rq_connection(app)
app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq-dashboard")

#import here to bypass circular imports
from api import sanity, post_process, conquest, jobs, database, weights, patientQA#, totalsegmentator

# Add blueprints
app.register_blueprint(main.bp)
app.register_blueprint(sanity.bp)
app.register_blueprint(post_process.bp)
app.register_blueprint(conquest.bp)
app.register_blueprint(jobs.bp)
app.register_blueprint(database.bp)
app.register_blueprint(weights.bp)
app.register_blueprint(patientQA.bp)
#app.register_blueprint(totalsegmentator.bp)

app.add_url_rule('/', endpoint='main')

# with App.app_context():
#     init_models(db)

CORS(app, resources={r"/api/*": {"origins": "*"}}) # Allow Cross-origin requests~
logger.info("App started")



