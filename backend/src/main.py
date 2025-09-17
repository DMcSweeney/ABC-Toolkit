"""
Abc-Spine main endpoints
"""
import os
from flask import Blueprint, request, make_response, jsonify

bp = Blueprint('main', __name__)


@bp.route('/hello', methods=["GET"])
def hello():
    res = make_response(jsonify({
        "message": "Welcome",
        "sender": "ABC"
    }), 200)
    return res