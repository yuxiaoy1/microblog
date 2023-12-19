from flask import Blueprint

api = Blueprint("api", __name__)

from app.api import errors, tokens, users  # noqa: E402, F401
