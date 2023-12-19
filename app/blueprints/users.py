from datetime import datetime, timezone

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import EditProfileForm, MessageForm
from app.models import Message, Notification, Post, User

users = Blueprint("users", __name__)


@users.get("/<username>")
@login_required
def profile(username):
    user = db.first_or_404(db.select(User).filter_by(username=username))
    posts = db.paginate(
        user.posts.select().order_by(Post.timestamp.desc()),
        per_page=current_app.config["POSTS_PER_PAGE"],
    )
    return render_template(
        "user/index.html",
        title=username,
        user=user,
        posts=posts,
    )


@users.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash("Your changes have been saved.")
        return redirect(url_for("users.edit_profile"))
    form.username.data = current_user.username
    form.about_me.data = current_user.about_me
    return render_template("user/edit_profile.html", title="Edit Profile", form=form)


@users.post("/follow/<username>")
@login_required
def follow(username):
    if g.empty_form.validate_on_submit():
        user = db.session.scalar(db.select(User).filter_by(username=username))
        if user is None:
            flash(f"User {username} not found.")
            return redirect(url_for("main.index"))
        if user == current_user:
            flash("You cannot follow yourself!")
            return redirect(url_for("users.profile", username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f"You are following {username}")
        return redirect(url_for("users.profile", username=username))
    return redirect(url_for("main.index"))


@users.post("/unfollow/<username>")
@login_required
def unfollow(username):
    if g.empty_form.validate_on_submit():
        user = db.session.scalar(db.select(User).filter_by(username=username))
        if user is None:
            flash(f"User {username} not found.")
            return redirect(url_for("main.index"))
        if user == current_user:
            flash("You cannot unfollow yourself!")
            return redirect(url_for("users.profile", username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f"You are not following {username}")
        return redirect(url_for("users.profile", username=username))
    return redirect(url_for("main.index"))


@users.get("/<username>/popup")
@login_required
def popup(username):
    user = db.first_or_404(db.select(User).filter_by(username=username))
    return render_template("user/popup.html", user=user)


@users.route("/send-message/<recipient>", methods=["GET", "POST"])
@login_required
def send_message(recipient):
    form = MessageForm()
    user = db.first_or_404(db.select(User).filter_by(username=recipient))
    if form.validate_on_submit():
        message = Message(author=current_user, recipient=user, body=form.message.data)
        db.session.add(message)
        user.add_notification("unread_message_count", user.unread_message_count)
        db.session.commit()
        flash("Your message has been sent.")
        return redirect(url_for("users.profile", username=recipient))
    return render_template(
        "user/send_message.html", title="Send Message", form=form, recipient=recipient
    )


@users.get("/messages")
@login_required
def messages():
    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification("unread_message_count", 0)
    db.session.commit()
    messages = db.paginate(
        current_user.messages_received.select().order_by(Message.timestamp.desc()),
        per_page=current_app.config["POSTS_PER_PAGE"],
    )
    return render_template("user/messages.html", title="Messages", messages=messages)


@users.get("/notifications")
@login_required
def notifications():
    since = request.args.get("since", 0.0, type=float)
    notifications = db.session.scalars(
        current_user.notifications.select()
        .filter(Notification.timestamp > since)
        .order_by(Notification.timestamp.asc())
    )
    return [
        {"name": n.name, "data": n.get_data(), "timestamp": n.timestamp}
        for n in notifications
    ]
