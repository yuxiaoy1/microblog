from datetime import datetime, timezone

import sqlalchemy as sa
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
from app.forms import EmptyForm, PostForm, SearchForm
from app.models import Post, User

main = Blueprint("main", __name__)


@main.before_app_request
def before_app_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
        g.search_form = SearchForm()
        g.empty_form = EmptyForm()


@main.route("/", methods=["GET", "POST"])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash("Your post is now live!")
        return redirect(url_for("main.index"))
    posts = db.paginate(
        current_user.following_posts(), per_page=current_app.config["POSTS_PER_PAGE"]
    )
    return render_template(
        "index.html",
        title="Home Page",
        form=form,
        posts=posts,
    )


@main.get("/explore")
@login_required
def explore():
    posts = db.paginate(
        db.select(Post).order_by(Post.timestamp.desc()),
        per_page=current_app.config["POSTS_PER_PAGE"],
    )
    return render_template(
        "index.html",
        title="Explore",
        posts=posts,
    )


@main.get("/search")
@login_required
def search():
    q = request.args.get("q")
    posts = db.paginate(
        db.select(Post)
        .filter(
            sa.or_(
                Post.body.like(f"%{q}%"), Post.author.has(User.username.like(f"%{q}%"))
            )
        )
        .order_by(Post.timestamp.desc()),
        per_page=current_app.config["POSTS_PER_PAGE"],
    )

    return render_template("search.html", title="Search", posts=posts, q=q)


@main.get("/export-posts")
@login_required
def export_post():
    if current_user.get_task_in_progress("export_posts"):
        flash("An export task is currently in progress")
    else:
        current_user.launch_task("export_posts", "Exporting post...")
        db.session.commit()
    return redirect(url_for("users.profile", username=current_user.username))
