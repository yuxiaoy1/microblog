import json
from threading import Thread

from flask import current_app, render_template
from flask_mailman import EmailMessage


def _send_async_mail(app, message):
    with app.app_context():
        message.send()


def send_mail(subject, body, to, attachments=None, sync=False):
    app = current_app._get_current_object()
    message = EmailMessage(subject, body, to=[to])
    message.content_subtype = "html"
    if attachments:
        for attachment in attachments:
            message.attach(*attachment)
    if sync:
        message.send()
    else:
        Thread(target=_send_async_mail, args=[app, message]).start()


def send_password_reset_mail(user):
    token = user.get_reset_password_token()
    send_mail(
        "[Microblog] Reset Your Psssword",
        render_template("email/reset_password.html", user=user, token=token),
        to=user.email,
    )


def send_posts_export_email(user, data):
    send_mail(
        "[Microblog] Your blog posts",
        render_template("email/export_posts.html", user=user),
        to=user.email,
        attachments=[
            ("posts.json", json.dumps({"posts": data}, indent=4), "application/json")
        ],
        sync=True,
    )
