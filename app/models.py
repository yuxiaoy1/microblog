import json
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import md5
from time import time
from typing import Optional

import jwt
import redis
import rq
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app, url_for
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

followers = db.Table(
    "followers",
    sa.Column("follower_id", sa.ForeignKey("user.id"), primary_key=True),
    sa.Column("following_id", sa.ForeignKey("user.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))
    posts: so.WriteOnlyMapped["Post"] = so.relationship(back_populates="author")
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[datetime] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    following: so.WriteOnlyMapped["User"] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.following_id == id),
        back_populates="followers",
    )
    followers: so.WriteOnlyMapped["User"] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.following_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates="following",
    )
    messages_sent: so.WriteOnlyMapped["Message"] = so.relationship(
        foreign_keys="Message.sender_id", back_populates="author"
    )
    messages_received: so.WriteOnlyMapped["Message"] = so.relationship(
        foreign_keys="Message.recipient_id", back_populates="recipient"
    )
    last_message_read_time: so.Mapped[Optional[datetime]]
    notifications: so.WriteOnlyMapped["Notification"] = so.relationship(
        back_populates="user"
    )
    tasks: so.WriteOnlyMapped["Task"] = so.relationship(back_populates="user")
    token: so.Mapped[Optional[str]] = so.mapped_column(
        sa.String(32), index=True, unique=True
    )
    token_expiration: so.Mapped[Optional[datetime]]

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)

    def avatar(self, size=128):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        return (
            db.session.scalar(self.following.select().filter_by(id=user.id)) is not None
        )

    @property
    def followers_count(self):
        return db.session.scalar(
            db.select(sa.func.count()).select_from(self.followers.select().subquery())
        )

    @property
    def following_count(self):
        return db.session.scalar(
            db.select(sa.func.count()).select_from(self.following.select().subquery())
        )

    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        return (
            db.select(Post)
            .join(Post.author.of_type(Author))
            .join(Author.followers.of_type(Follower), isouter=True)
            .where(sa.or_(Follower.id == self.id, Author.id == self.id))
            .group_by(Post)
            .order_by(Post.timestamp.desc())
        )

    @property
    def unread_message_count(self):
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return db.session.scalar(
            db.select(sa.func.count()).select_from(
                db.select(Message)
                .filter_by(recipient=self)
                .filter(Message.timestamp > last_read_time)
                .subquery()
            )
        )

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {"reset_password": self.id, "exp": time() + expires_in},
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )["reset_password"]
        except Exception:
            return
        return db.session.get(User, id)

    def add_notification(self, name, data):
        db.session.execute(self.notifications.delete().filter_by(name=name))
        n = Notification(name=name, payload=json.dumps(data), user=self)
        db.session.add(n)
        return n

    def launch_task(self, name, description, *args, **kwargs):
        rq_job = current_app.task_queue.enqueue(
            f"app.tasks.{name}", self.id, *args, **kwargs
        )
        task = Task(id=rq_job.get_id(), name=name, description=description, user=self)
        db.session.add(task)
        return task

    def get_tasks_in_progress(self):
        return db.session.scalars(self.tasks.select().filter_by(complete=False))

    def get_task_in_progress(self, name):
        return db.session.scalar(
            self.tasks.select().filter_by(name=name, complete=False)
        )

    @property
    def posts_count(self):
        return db.session.scalar(
            db.select(sa.func.count()).select_from(self.posts.select().subquery())
        )

    def to_dict(self, include_email=False):
        data = {
            "id": self.id,
            "username": self.username,
            "last_seen": self.last_seen.replace(tzinfo=timezone.utc).isoformat(),
            "about_me": self.about_me,
            "posts_count": self.posts_count,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "_links": {
                "self": url_for("api.get_user", id=self.id),
                "followers": url_for("api.get_followers", id=self.id),
                "following": url_for("api.get_following", id=self.id),
                "avatar": self.avatar(128),
            },
        }
        if include_email:
            data["email"] = self.email
        return data

    def from_dict(self, data, new_user=False):
        for field in ("username", "email", "about_me"):
            if field in data:
                setattr(self, field, data[field])
        if new_user and "password" in data:
            self.set_password(data["password"])

    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = db.paginate(query, page=page, per_page=per_page, error_out=False)
        data = {
            "items": [item.to_dict() for item in resources.items],
            "_meta": {
                "page": page,
                "per_page": per_page,
                "total_pages": resources.pages,
                "total_items": resources.total,
            },
            "_links": {
                "self": url_for(endpoint, page=page, per_page=per_page, **kwargs),
                "next": url_for(endpoint, page=page + 1, per_page=per_page, **kwargs)
                if resources.has_next
                else None,
                "prev": url_for(endpoint, page=page - 1, per_page=per_page, **kwargs)
                if resources.has_prev
                else None,
            },
        }
        return data

    def get_token(self, expires_in=3600):
        now = datetime.now(timezone.utc)
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = secrets.token_hex(16)
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = db.session.scalar(db.select(User).filter_by(token=token))
        if user and user.token_expiration.replace(tzinfo=timezone.utc) > datetime.now(
            timezone.utc
        ):
            return user


class Post(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc)
    )
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("user.id"), index=True)
    author: so.Mapped["User"] = so.relationship(back_populates="posts")


class Message(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("user.id"), index=True)
    recipient_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("user.id"), index=True
    )
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc)
    )
    author: so.Mapped["User"] = so.relationship(
        foreign_keys=[sender_id], back_populates="messages_sent"
    )
    recipient: so.Mapped["User"] = so.relationship(
        foreign_keys=[recipient_id], back_populates="messages_received"
    )


class Notification(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("user.id"), index=True)
    timestamp: so.Mapped[float] = so.mapped_column(index=True, default=time)
    payload: so.Mapped[str]
    user: so.Mapped["User"] = so.relationship(back_populates="notifications")

    def get_data(self):
        return json.loads(self.payload)


class Task(db.Model):
    id: so.Mapped[str] = so.mapped_column(sa.String(36), primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("user.id"))
    complete: so.Mapped[bool] = so.mapped_column(default=False)
    user: so.Mapped["User"] = so.relationship(back_populates="tasks")

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get("progress", 0) if job is not None else 100
