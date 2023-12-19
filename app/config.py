import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "secret")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABSE_URL", "sqlite:///" + os.path.join(basedir, "db.sqlite")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    POSTS_PER_PAGE = 5

    REDIS_URL = os.getenv("REDIS_URL", "redis://")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = os.getenv("MAIL_PORT", 8025)
