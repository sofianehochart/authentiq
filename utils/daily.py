import json
import random
from datetime import date
from extensions import db
from models import Question, DailySet


def get_or_create_daily_set():
    today = date.today()
    existing = DailySet.query.filter_by(date=today).first()
    if existing and existing.get_question_ids():
        return existing
    if existing:
        db.session.delete(existing)
        db.session.commit()

    ai_qs = (
        Question.query.filter_by(is_real=False, is_approved=True)
        .order_by(db.func.random()).limit(5).all()
    )
    real_qs = (
        Question.query.filter_by(is_real=True, is_approved=True)
        .order_by(db.func.random()).limit(5).all()
    )
    selected_ids = [q.id for q in ai_qs] + [q.id for q in real_qs]
    random.shuffle(selected_ids)

    daily_set = DailySet(date=today, question_ids=json.dumps(selected_ids))
    db.session.add(daily_set)
    db.session.commit()
    return daily_set
