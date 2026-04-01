import json
import random
from datetime import date
from extensions import db
from models import Question, DailySet


def get_or_create_daily_set():
    today = date.today()
    existing = DailySet.query.filter_by(date=today).first()
    if existing:
        return existing

    themes = ['Celebrity', 'Politics', 'Sports', 'Tech', 'Viral']
    selected_ids = []

    for theme in themes:
        ai_q = Question.query.filter_by(theme=theme, is_ai=True).order_by(db.func.random()).first()
        real_q = Question.query.filter_by(theme=theme, is_ai=False).order_by(db.func.random()).first()
        if ai_q:
            selected_ids.append(ai_q.id)
        if real_q:
            selected_ids.append(real_q.id)

    random.shuffle(selected_ids)
    selected_ids = selected_ids[:10]

    daily_set = DailySet(date=today, question_ids=json.dumps(selected_ids))
    db.session.add(daily_set)
    db.session.commit()
    return daily_set
