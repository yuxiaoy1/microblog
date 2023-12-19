from flask import Blueprint, render_template, request

from app.api.errors import error_response as api_error_response

errors = Blueprint("errors", __name__)


def wants_json_response():
    return (
        request.accept_mimetypes["application/json"]
        >= request.accept_mimetypes["text/html"]
    )


@errors.app_errorhandler(400)
def bad_request(error):
    if wants_json_response():
        return api_error_response(404)
    return render_template("error/400.html"), 400


@errors.app_errorhandler(404)
def not_found(error):
    if wants_json_response():
        return api_error_response(404)
    return render_template("error/404.html"), 404


@errors.app_errorhandler(500)
def internal_server_error(error):
    if wants_json_response():
        return api_error_response(500)
    return render_template("error/500.html"), 500
