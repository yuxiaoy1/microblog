import rq
from flask import Flask
from redis import Redis

from app import models
from app.api import api
from app.blueprints.auth import auth
from app.blueprints.commands import commands
from app.blueprints.errors import errors
from app.blueprints.main import main
from app.blueprints.users import users
from app.config import Config
from app.extensions import bootstrap, db, login, mail, moment


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    app.redis = Redis.from_url(app.config["REDIS_URL"])
    app.task_queue = rq.Queue("microblog-tasks", connection=app.redis)

    register_extensions(app)
    register_blueprints(app)
    register_shell_context(app)

    return app


def register_extensions(app: Flask):
    db.init_app(app)
    login.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    mail.init_app(app)


def register_blueprints(app: Flask):
    app.register_blueprint(commands)
    app.register_blueprint(errors)
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(users, url_prefix="/user")
    app.register_blueprint(api, url_prefix="/api")


def register_shell_context(app: Flask):
    @app.shell_context_processor
    def shell_context():
        ctx = {"db": db}
        for attr in dir(models):
            model = getattr(models, attr)
            if hasattr(model, "__bases__") and db.Model in getattr(model, "__bases__"):
                ctx[attr] = model
        return ctx
