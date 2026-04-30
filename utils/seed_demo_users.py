"""Seed demo users + completed quiz attempts so the leaderboard looks alive.

Idempotent: skips users that already exist; skips attempts already completed today.
"""

from datetime import datetime, timedelta, date

from werkzeug.security import generate_password_hash

from extensions import db
from models import User, QuizAttempt
from utils.daily import get_or_create_daily_set


DEMO_USERS = [
    ("alex_yale", "#7c3aed", True, 11420),
    ("jordan_sm", "#0ea5e9", True, 9870),
    ("taylor_p", "#10b981", False, 8650),
    ("morgan_k", "#f59e0b", True, 8120),
    ("sam_lee", "#ef4444", False, 7340),
    ("casey_w", "#ec4899", False, 6780),
    ("nico_b", "#7c3aed", True, 6210),
    ("riley_o", "#0ea5e9", False, 5640),
    ("emery_v", "#10b981", False, 4980),
    ("lane_h", "#f59e0b", False, 4350),
    ("priya_r", "#ec4899", True, 3820),
    ("dev_choi", "#ef4444", False, 3110),
]


def seed_demo_users(password: str = "demo1234") -> None:
    daily_set = get_or_create_daily_set()
    today = date.today()
    base_time = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)

    created = 0
    skipped = 0
    for offset, (username, colour, is_premium, score) in enumerate(DEMO_USERS):
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                avatar_colour=colour,
                is_premium=is_premium,
            )
            db.session.add(user)
            db.session.flush()
            created += 1
        else:
            user.is_premium = is_premium
            user.avatar_colour = colour

        existing = (
            QuizAttempt.query.filter_by(user_id=user.id, daily_set_id=daily_set.id)
            .filter(QuizAttempt.completed_at.isnot(None))
            .first()
        )
        if existing:
            skipped += 1
            continue

        completed_at = base_time + timedelta(minutes=offset * 7)
        attempt = QuizAttempt(
            user_id=user.id,
            daily_set_id=daily_set.id,
            score=score,
            started_at=completed_at - timedelta(minutes=2),
            completed_at=completed_at,
        )
        db.session.add(attempt)

    db.session.commit()
    print(f"Demo users — created: {created}, attempts skipped (already had): {skipped}, total: {len(DEMO_USERS)}")
    print(f"All demo passwords: {password}")
