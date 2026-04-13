from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import QuizAttempt
from utils.tournament import best_finish_for_user

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
            label = (ans.question.category or '').title() or 'Unknown'
            if label not in theme_stats:
                theme_stats[label] = {'correct': 0, 'total': 0}
            theme_stats[label]['total'] += 1
            if ans.correct:
                theme_stats[label]['correct'] += 1
    for theme in theme_stats:
        t = theme_stats[theme]
        t['accuracy'] = round(100 * t['correct'] / t['total']) if t['total'] else 0

    recent = attempts[:7]

    raw_badge = best_finish_for_user(current_user.id)
    tournament_badge = None
    if raw_badge:
        cat = raw_badge.get('category') or ''
        rk = raw_badge['rank']
        if 11 <= (rk % 100) <= 13:
            rank_label = f'{rk}th'
        else:
            suf = {1: 'st', 2: 'nd', 3: 'rd'}.get(rk % 10, 'th')
            rank_label = f'{rk}{suf}'
        tournament_badge = {
            'rank': rk,
            'rank_label': rank_label,
            'category_label': 'Mixed' if cat == 'mixed' else (cat.title() if cat else ''),
            'tournament_id': raw_badge.get('tournament_id'),
        }

    return render_template('profile.html',
        attempts=attempts,
        lifetime_accuracy=lifetime_accuracy,
        streak=streak,
        theme_stats=theme_stats,
        recent=recent,
        tournament_badge=tournament_badge,
    )
