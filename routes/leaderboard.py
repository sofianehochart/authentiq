from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import User, CircleMember, QuizAttempt

leaderboard_bp = Blueprint('leaderboard', __name__)


def _week_bounds():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


@leaderboard_bp.route('/leaderboard')
@login_required
def leaderboard():
    monday, sunday = _week_bounds()

    from extensions import db
    from sqlalchemy import func
    global_rows = (
        db.session.query(
            User.username,
            User.avatar_colour,
            User.is_premium,
            func.sum(QuizAttempt.score).label('weekly'),
        )
        .join(QuizAttempt, QuizAttempt.user_id == User.id)
        .filter(QuizAttempt.completed_at.isnot(None))
        .filter(func.date(QuizAttempt.completed_at) >= monday)
        .filter(func.date(QuizAttempt.completed_at) <= sunday)
        .group_by(User.id)
        .order_by(db.text('weekly DESC'))
        .limit(20)
        .all()
    )

    circle_rows = []
    membership = CircleMember.query.filter_by(user_id=current_user.id).first()
    circle = None
    if membership:
        from models import Circle
        circle = db.session.get(Circle, membership.circle_id)
        member_ids = [m.user_id for m in CircleMember.query.filter_by(circle_id=circle.id).all()]
        circle_rows = (
            db.session.query(
                User.username,
                User.avatar_colour,
                User.is_premium,
                func.sum(QuizAttempt.score).label('weekly'),
            )
            .join(QuizAttempt, QuizAttempt.user_id == User.id)
            .filter(User.id.in_(member_ids))
            .filter(QuizAttempt.completed_at.isnot(None))
            .filter(func.date(QuizAttempt.completed_at) >= monday)
            .filter(func.date(QuizAttempt.completed_at) <= sunday)
            .group_by(User.id)
            .order_by(db.text('weekly DESC'))
            .all()
        )

    return render_template('leaderboard.html',
        global_rows=global_rows,
        circle_rows=circle_rows,
        circle=circle,
        week_start=monday
    )
