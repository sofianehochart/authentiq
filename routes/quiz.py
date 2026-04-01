from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user
from extensions import db
from models import Question, QuizAttempt, QuizAnswer
from utils.daily import get_or_create_daily_set
from utils.scoring import calculate_points

quiz_bp = Blueprint('quiz', __name__)


@quiz_bp.route('/home')
@login_required
def home():
    daily_set = get_or_create_daily_set()
    today_attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        daily_set_id=daily_set.id
    ).filter(QuizAttempt.completed_at.isnot(None)).first()
    return render_template('home.html', today_attempt=today_attempt, daily_set=daily_set)


@quiz_bp.route('/quiz')
@login_required
def quiz():
    daily_set = get_or_create_daily_set()

    completed = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        daily_set_id=daily_set.id
    ).filter(QuizAttempt.completed_at.isnot(None)).first()
    if completed:
        return redirect(url_for('quiz.results', attempt_id=completed.id))

    attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        daily_set_id=daily_set.id,
        completed_at=None
    ).first()
    if not attempt:
        attempt = QuizAttempt(user_id=current_user.id, daily_set_id=daily_set.id)
        db.session.add(attempt)
        db.session.commit()

    answered_ids = {a.question_id for a in attempt.answers}
    question_ids = daily_set.get_question_ids()
    remaining = [qid for qid in question_ids if qid not in answered_ids]

    if not remaining:
        attempt.completed_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('quiz.results', attempt_id=attempt.id))

    question = db.session.get(Question, remaining[0])
    question_number = len(answered_ids) + 1

    return render_template('quiz.html',
        question=question,
        question_number=question_number,
        total=len(question_ids),
        attempt_id=attempt.id
    )


@quiz_bp.route('/quiz/answer', methods=['POST'])
@login_required
def answer():
    attempt_id = request.form.get('attempt_id', type=int)
    question_id = request.form.get('question_id', type=int)
    answer_val = request.form.get('answer')
    response_time_ms = request.form.get('response_time_ms', type=int, default=15000)

    attempt = db.session.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        abort(403)

    if attempt.completed_at is not None:
        return redirect(url_for('quiz.results', attempt_id=attempt.id))

    daily_set = attempt.daily_set
    if question_id not in daily_set.get_question_ids():
        abort(400)

    if QuizAnswer.query.filter_by(attempt_id=attempt.id, question_id=question_id).first():
        return redirect(url_for('quiz.quiz'))

    question = db.session.get(Question, question_id)
    if not question:
        abort(404)

    if answer_val not in ('ai', 'real', 'timeout'):
        abort(400)

    response_time_ms = max(0, min(15000, response_time_ms))

    if answer_val == 'timeout':
        user_answer = None
        correct = False
    else:
        user_answer = (answer_val == 'ai')
        correct = (user_answer == question.is_ai)

    points = calculate_points(correct, response_time_ms)

    quiz_answer = QuizAnswer(
        attempt_id=attempt.id,
        question_id=question_id,
        answer=user_answer,
        correct=correct,
        response_time_ms=response_time_ms,
        points_earned=points
    )
    db.session.add(quiz_answer)
    attempt.score += points

    answered_count = QuizAnswer.query.filter_by(attempt_id=attempt.id).count() + 1
    if answered_count >= len(daily_set.get_question_ids()):
        attempt.completed_at = datetime.utcnow()

    db.session.commit()
    return redirect(url_for('quiz.quiz'))


@quiz_bp.route('/quiz/results/<int:attempt_id>')
@login_required
def results(attempt_id):
    attempt = db.session.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        abort(403)
    return render_template('results.html', attempt=attempt)
