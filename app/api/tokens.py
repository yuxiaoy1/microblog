from app.api import api
from app.api.auth import basic_auth, token_auth
from app.extensions import db


@api.post("/tokens")
@basic_auth.login_required
def get_token():
    token = basic_auth.current_user().get_token()
    db.session.commit()
    return {"token": token}


@api.delete("/tokens")
@token_auth.login_required
def revoke_token():
    token_auth.current_user().revoke_token()
    db.session.commit()
    return "", 204
