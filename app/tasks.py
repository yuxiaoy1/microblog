import sys
import time

import sqlalchemy as sa
from rq import get_current_job

from app import create_app
from app.emails import send_posts_export_email
from app.extensions import db
from app.models import Post, Task, User

app = create_app()
app.app_context().push()


def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta["progress"] = progress
        job.save_meta()
        task = db.session.get(Task, job.get_id())
        task.user.add_notification(
            "task_progress", {"task_id": job.get_id(), "progress": progress}
        )
        if progress >= 100:
            task.complete = True
        db.session.commit()


def export_posts(user_id):
    try:
        user = db.session.get(User, user_id)
        _set_task_progress(0)
        data = []
        i = 0
        total_posts = db.session.scalar(
            db.select(sa.func.count()).select_from(user.posts.select().subquery())
        )
        for post in db.session.scalars(
            user.posts.select().order_by(Post.timestamp.asc())
        ):
            data.append(
                {"body": post.body, "timestamp": post.timestamp.isoformat() + "Z"}
            )
            time.sleep(5)
            i += 1
            _set_task_progress(100 * i // total_posts)
        send_posts_export_email(user, data)
    except Exception:
        print("Unhandled exception", sys.exc_info())
    finally:
        _set_task_progress(100)
