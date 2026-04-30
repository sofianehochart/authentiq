from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import func, case
from extensions import db
from models import Question, QuizAttempt, QuizAnswer, GameSession, QuestionResult
from utils.daily import get_or_create_daily_set
from utils.explanations import explanation_for
from utils.scoring import calculate_points

quiz_bp = Blueprint('quiz', __name__)


def _get_or_create_daily_game_session(user_id: int) -> GameSession:
    today = date.today()
    open_session = (
        GameSession.query.filter_by(user_id=user_id, mode='daily', completed_at=None)
        .filter(func.date(GameSession.started_at) == today)
        .order_by(GameSession.id.desc())
        .first()
    )
    if open_session:
        return open_session
    session = GameSession(
        user_id=user_id,
        category=None,
        mode='daily',
        total_questions=0,
        correct_answers=0,
        score=0,
    )
    db.session.add(session)
    db.session.flush()
    return session


def _refresh_game_session_rollups(session: GameSession, attempt: QuizAttempt) -> None:
    totals = (
        db.session.query(
            func.count(QuestionResult.id),
            func.sum(case((QuestionResult.is_correct.is_(True), 1), else_=0)),
            func.avg(QuestionResult.response_time_ms),
        )
        .filter(QuestionResult.session_id == session.id)
        .one()
    )
    n = int(totals[0] or 0)
    c = int(totals[1] or 0)
    avg = totals[2]
    session.total_questions = n
    session.correct_answers = c
    session.score = int(attempt.score or 0)
    session.avg_response_time_ms = int(round(float(avg))) if avg is not None and n else None


def _record_question_result(
    *,
    user_id: int,
    question: Question,
    answer_val: str,
    user_answer_bool,
    correct: bool,
    response_time_ms: int,
    attempt: QuizAttempt,
    quiz_just_completed: bool,
) -> None:
    if answer_val == 'timeout':
        ua_label = 'timeout'
    else:
        ua_label = 'ai' if user_answer_bool else 'real'

    fmt = (question.format or 'tweet').strip().lower()
    if len(fmt) > 32:
        fmt = fmt[:32]

    game_session = _get_or_create_daily_game_session(user_id)
    db.session.add(
        QuestionResult(
            session_id=game_session.id,
            question_id=question.id,
            user_answer=ua_label,
            is_correct=bool(correct),
            response_time_ms=int(response_time_ms),
            format=fmt,
        )
    )
    _refresh_game_session_rollups(game_session, attempt)
    if quiz_just_completed:
        game_session.completed_at = datetime.utcnow()
        _refresh_game_session_rollups(game_session, attempt)


@quiz_bp.route('/home')
@login_required
def home():
    daily_set = get_or_create_daily_set()
    today_attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        daily_set_id=daily_set.id
    ).filter(QuizAttempt.completed_at.isnot(None)).first()
    show_premium_upsell = bool(
        not current_user.is_premium and not session.get("premium_upsell_dismissed")
    )
    return render_template(
        'home.html',
        today_attempt=today_attempt,
        daily_set=daily_set,
        show_premium_upsell=show_premium_upsell,
    )


@quiz_bp.post('/home/dismiss-premium-upsell')
@login_required
def dismiss_premium_upsell():
    session['premium_upsell_dismissed'] = True
    session.modified = True
    return ('', 204)


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
        # is_real True => human-authored; user "ai" is correct when content is not real
        correct = user_answer != question.is_real

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
    quiz_just_completed = answered_count >= len(daily_set.get_question_ids())
    if quiz_just_completed:
        attempt.completed_at = datetime.utcnow()

    _record_question_result(
        user_id=current_user.id,
        question=question,
        answer_val=answer_val,
        user_answer_bool=user_answer,
        correct=correct,
        response_time_ms=response_time_ms,
        attempt=attempt,
        quiz_just_completed=quiz_just_completed,
    )

    db.session.commit()
    return redirect(url_for('quiz.quiz'))


@quiz_bp.route('/quiz/answer_json', methods=['POST'])
@login_required
def answer_json():
    attempt_id = request.form.get('attempt_id', type=int)
    question_id = request.form.get('question_id', type=int)
    answer_val = request.form.get('answer')
    response_time_ms = request.form.get('response_time_ms', type=int, default=15000)

    attempt = db.session.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        abort(403)

    if attempt.completed_at is not None:
        return jsonify({"redirect_url": url_for('quiz.results', attempt_id=attempt.id)}), 200

    daily_set = attempt.daily_set
    if question_id not in daily_set.get_question_ids():
        abort(400)

    if QuizAnswer.query.filter_by(attempt_id=attempt.id, question_id=question_id).first():
        return jsonify({"redirect_url": url_for('quiz.quiz')}), 200

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
        correct = user_answer != question.is_real

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
    quiz_just_completed = answered_count >= len(daily_set.get_question_ids())
    if quiz_just_completed:
        attempt.completed_at = datetime.utcnow()

    _record_question_result(
        user_id=current_user.id,
        question=question,
        answer_val=answer_val,
        user_answer_bool=user_answer,
        correct=correct,
        response_time_ms=response_time_ms,
        attempt=attempt,
        quiz_just_completed=quiz_just_completed,
    )

    db.session.commit()

    correct_answer = 'real' if question.is_real else 'ai'
    explanation = explanation_for(question)
    next_url = url_for('quiz.quiz') if attempt.completed_at is None else url_for('quiz.results', attempt_id=attempt.id)

    return jsonify({
        "correct": bool(correct),
        "points": int(points),
        "correct_answer": correct_answer,
        "explanation": explanation,
        "next_url": next_url,
    }), 200


@quiz_bp.route('/quiz/results/<int:attempt_id>')
@login_required
def results(attempt_id):
    attempt = db.session.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        abort(403)
    return render_template('results.html', attempt=attempt)
