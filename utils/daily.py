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

    categories = ['celebrity', 'politics', 'sports', 'tech', 'viral']
    selected_ids = []

    for category in categories:
        ai_q = (
            Question.query.filter_by(category=category, is_real=False, is_approved=True)
            .order_by(db.func.random()).first()
        )
        real_q = (
            Question.query.filter_by(category=category, is_real=True, is_approved=True)
            .order_by(db.func.random()).first()
        )
        if ai_q:
            selected_ids.append(ai_q.id)
        if real_q:
            selected_ids.append(real_q.id)

    random.shuffle(selected_ids)

    daily_set = DailySet(date=today, question_ids=json.dumps(selected_ids))
    db.session.add(daily_set)
    db.session.commit()
    return daily_set
