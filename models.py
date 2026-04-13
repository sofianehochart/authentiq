import json
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar_colour = db.Column(db.String(7), nullable=False, default='#7c3aed')
    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    memberships = db.relationship('CircleMember', backref='user', lazy=True)
    game_sessions = db.relationship('GameSession', back_populates='user', lazy=True)
    challenges_as_challenger = db.relationship(
        'Challenge', foreign_keys='Challenge.challenger_id', back_populates='challenger', lazy=True
    )
    challenges_as_opponent = db.relationship(
        'Challenge', foreign_keys='Challenge.opponent_id', back_populates='opponent', lazy=True
    )
    tournament_entries = db.relationship('TournamentEntry', back_populates='user', lazy=True)


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
    category = db.Column(db.String(32), nullable=False)
    format = db.Column(db.String(32), nullable=False)
    persona = db.Column(db.String(120), nullable=False)
    handle = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_real = db.Column(db.Boolean, nullable=False)
    source_date = db.Column(db.String(64), nullable=False, default='')
    explanation = db.Column(db.Text, nullable=False, default='')
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    scheduled_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DailySet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    question_ids = db.Column(db.Text, nullable=False)

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
    answer = db.Column(db.Boolean, nullable=True)
    correct = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=False)
    points_earned = db.Column(db.Integer, nullable=False)

    question = db.relationship('Question')


class GameSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(32), nullable=True)
    mode = db.Column(db.String(32), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    correct_answers = db.Column(db.Integer, nullable=False, default=0)
    score = db.Column(db.Integer, nullable=False, default=0)
    avg_response_time_ms = db.Column(db.Integer, nullable=True)

    user = db.relationship('User', back_populates='game_sessions')
    question_results = db.relationship('QuestionResult', back_populates='session', lazy=True)


class QuestionResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('game_session.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_answer = db.Column(db.String(8), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=False)
    format = db.Column(db.String(32), nullable=False)

    session = db.relationship('GameSession', back_populates='question_results')
    question = db.relationship('Question')


class ChallengeAnswer(db.Model):
    __tablename__ = 'challenge_answer'
    __table_args__ = (
        UniqueConstraint('challenge_id', 'user_id', 'question_id', name='uq_challenge_answer_user_question'),
    )

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.Boolean, nullable=True)
    correct = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=False)
    points_earned = db.Column(db.Integer, nullable=False)

    challenge = db.relationship('Challenge', back_populates='answer_rows')
    question = db.relationship('Question')


class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challenger_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    opponent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    question_ids = db.Column(db.JSON, nullable=False)
    challenger_score = db.Column(db.Integer, nullable=True)
    opponent_score = db.Column(db.Integer, nullable=True)
    challenger_correct_count = db.Column(db.Integer, nullable=True)
    opponent_correct_count = db.Column(db.Integer, nullable=True)
    challenger_time_ms = db.Column(db.Integer, nullable=True)
    opponent_time_ms = db.Column(db.Integer, nullable=True)
    challenger_completed_at = db.Column(db.DateTime, nullable=True)
    opponent_completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(16), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    challenger = db.relationship('User', foreign_keys=[challenger_id], back_populates='challenges_as_challenger')
    opponent = db.relationship('User', foreign_keys=[opponent_id], back_populates='challenges_as_opponent')
    answer_rows = db.relationship('ChallengeAnswer', back_populates='challenge', lazy=True)


class TournamentAnswer(db.Model):
    __tablename__ = 'tournament_answer'
    __table_args__ = (
        UniqueConstraint('tournament_id', 'user_id', 'question_id', name='uq_tournament_answer_user_q'),
    )

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.Boolean, nullable=True)
    correct = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=False)
    points_earned = db.Column(db.Integer, nullable=False)

    tournament = db.relationship('Tournament', back_populates='answer_rows')
    question = db.relationship('Question')


class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(32), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='upcoming')
    question_ids = db.Column(db.JSON, nullable=True)

    entries = db.relationship('TournamentEntry', back_populates='tournament', lazy=True)
    answer_rows = db.relationship('TournamentAnswer', back_populates='tournament', lazy=True)


class TournamentEntry(db.Model):
    __table_args__ = (
        UniqueConstraint('tournament_id', 'user_id', name='uq_tournament_entry_user'),
    )

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    accuracy = db.Column(db.Float, nullable=True)
    time_ms = db.Column(db.Integer, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    tournament = db.relationship('Tournament', back_populates='entries')
    user = db.relationship('User', back_populates='tournament_entries')
