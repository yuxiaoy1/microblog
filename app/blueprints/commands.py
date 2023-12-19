from flask import Blueprint

from app.extensions import db

commands = Blueprint("commands", __name__, cli_group=None)


@commands.cli.command()
def initdb():
    """Create database."""
    db.drop_all()
    db.create_all()
    print("Database created.")


@commands.cli.command()
def initmail():
    """Start email server."""
    import subprocess

    subprocess.call(
        "aiosmtpd -n -c aiosmtpd.handlers.Debugging -l localhost:8025", shell=True
    )
