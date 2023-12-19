from flask import abort, request, url_for

from app.api import api
from app.api.auth import token_auth
from app.api.errors import bad_request
from app.extensions import db
from app.models import User


@api.get("/users/<int:id>")
@token_auth.login_required
def get_user(id):
    return db.get_or_404(User, id).to_dict()


@api.get("/users")
@token_auth.login_required
def get_users():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("page", 10, type=int), 100)
    return User.to_collection_dict(db.select(User), page, per_page, "api.get_users")


@api.get("/users/<int:id>/followers")
@token_auth.login_required
def get_followers(id):
    user = db.get_or_404(User, id)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("page", 10, type=int), 100)
    return User.to_collection_dict(
        user.followers.select(), page, per_page, "api.get_followers", id=id
    )


@api.get("/users/<int:id>/following")
@token_auth.login_required
def get_following(id):
    user = db.get_or_404(User, id)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("page", 10, type=int), 100)
    return User.to_collection_dict(
        user.following.select(), page, per_page, "api.get_following", id=id
    )


@api.post("/users")
def create_user():
    data = request.get_json()
    if "username" not in data or "email" not in data or "password" not in data:
        return bad_request("must include username, email and password fields")
    if db.session.scalar(db.select(User).filter_by(username=data["username"])):
        return bad_request("please use a different username")
    if db.session.scalar(db.select(User).filter_by(email=data["email"])):
        return bad_request("please use a different email address")
    user = User()
    user.from_dict(data, new_user=True)
    db.session.add(user)
    db.session.commit()
    return user.to_dict(), 201, {"Location": url_for("api.get_user", id=user.id)}


@api.put("/users/<int:id>")
@token_auth.login_required
def update_user(id):
    if token_auth.current_user().id != id:
        abort(403)
    user = db.get_or_404(User, id)
    data = request.get_json()
    if (
        "username" in data
        and data["username"] != user.username
        and db.session.scalar(db.select(User).filter_by(username=data["username"]))
    ):
        return bad_request("please use a different username")
    if (
        "email" in data
        and data["email"] != user.email
        and db.session.scalar(db.select(User).filter_by(email=data["email"]))
    ):
        return bad_request("please use a different email address")
    user.from_dict(data)
    db.session.commit()
    return user.to_dict()
