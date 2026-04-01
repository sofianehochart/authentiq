from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import QuizAttempt

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile')
@login_required
def profile():
    attempts = QuizAttempt.query.filter_by(
        user_id=current_user.id
    ).filter(QuizAttempt.completed_at.isnot(None)).order_by(QuizAttempt.completed_at.desc()).all()

    total_answers = sum(len(a.answers) for a in attempts)
    correct_answers = sum(ans.correct for a in attempts for ans in a.answers)
    lifetime_accuracy = round(100 * correct_answers / total_answers) if total_answers else 0

    played_dates = {a.completed_at.date() for a in attempts}
    streak = 0
    check = date.today()
    while check in played_dates:
        streak += 1
        check -= timedelta(days=1)

    theme_stats = {}
    for attempt in attempts:
        for ans in attempt.answers:
            theme = ans.question.theme
            if theme not in theme_stats:
                theme_stats[theme] = {'correct': 0, 'total': 0}
            theme_stats[theme]['total'] += 1
            if ans.correct:
                theme_stats[theme]['correct'] += 1
    for theme in theme_stats:
        t = theme_stats[theme]
        t['accuracy'] = round(100 * t['correct'] / t['total']) if t['total'] else 0

    recent = attempts[:7]

    return render_template('profile.html',
        attempts=attempts,
        lifetime_accuracy=lifetime_accuracy,
        streak=streak,
        theme_stats=theme_stats,
        recent=recent
    )
