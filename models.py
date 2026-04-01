import json
from datetime import datetime
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar_colour = db.Column(db.String(7), nullable=False, default='#7c3aed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    memberships = db.relationship('CircleMember', backref='user', lazy=True)


class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    invite_code = db.Column(db.String(6), unique=True, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('CircleMember', backref='circle', lazy=True)


class CircleMember(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), primary_key=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    theme = db.Column(db.String(50), nullable=False)
    format = db.Column(db.String(50), nullable=False)   # tweet, linkedin, news_quote, reddit
    content = db.Column(db.Text, nullable=False)
    author_label = db.Column(db.String(100), nullable=False)
    is_ai = db.Column(db.Boolean, nullable=False)
    difficulty = db.Column(db.Integer, default=2)


class DailySet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    question_ids = db.Column(db.Text, nullable=False)   # JSON array

    def get_question_ids(self):
        return json.loads(self.question_ids)


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    daily_set_id = db.Column(db.Integer, db.ForeignKey('daily_set.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    answers = db.relationship('QuizAnswer', backref='attempt', lazy=True)
    daily_set = db.relationship('DailySet')


class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempt.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.Boolean, nullable=True)       # NULL = timed out
    correct = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=False)
    points_earned = db.Column(db.Integer, nullable=False)

    question = db.relationship('Question')
