from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from flask_mailman import Mail
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login = LoginManager()
bootstrap = Bootstrap5()
moment = Moment()
mail = Mail()


@login.user_loader
def load_user(id):
    from app.models import User

    return db.session.get(User, id)


login.login_view = "auth.login"
