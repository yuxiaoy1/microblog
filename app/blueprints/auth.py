from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.emails import send_password_reset_mail
from app.extensions import db
from app.forms import (
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
    ResetPasswordRequestForm,
)
from app.models import User

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).filter_by(username=form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("auth.login"))
        login_user(user, remember=form.remember_me.data)
        next = request.args.get("next")
        if not next or urlsplit(next).netloc != "":
            next = url_for("main.index")
        return redirect(next)
    return render_template("auth/login.html", title="Sign In", form=form)


@auth.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Congratulations, you are now a registered user!")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", title="Register", form=form)


@auth.route("/reset-password", methods=["GET", "POST"])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).filter_by(email=form.email.data))
        if user:
            send_password_reset_mail(user)
        flash("Check your email for the instructions to reset your password")
        return redirect(url_for("auth.login"))
    return render_template(
        "auth/reset_password_request.html", title="Reset Password", form=form
    )


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for("main.index"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
