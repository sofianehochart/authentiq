from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import User, Question, Challenge, ChallengeAnswer
from utils.explanations import explanation_for
from utils.scoring import calculate_points

challenge_bp = Blueprint("challenge", __name__, url_prefix="/challenge")

CATEGORIES = ("sports", "politics", "celebrity")
TOTAL_CHALLENGE_Q = 5


def _winner_side(ch: Challenge) -> str | None:
    if ch.status != "complete" or ch.challenger_score is None or ch.opponent_score is None:
        return None
    cs, os_ = ch.challenger_score, ch.opponent_score
    if cs > os_:
        return "challenger"
    if os_ > cs:
        return "opponent"
    ct = ch.challenger_time_ms if ch.challenger_time_ms is not None else 10**12
    ot = ch.opponent_time_ms if ch.opponent_time_ms is not None else 10**12
    if ct < ot:
        return "challenger"
    if ot < ct:
        return "opponent"
    return "tie"


def _history_label(ch: Challenge, as_challenger: bool) -> str:
    if ch.status == "pending":
        return "Your run in progress" if as_challenger else "Challenger is playing"
    if ch.status == "active":
        return "Waiting for opponent" if as_challenger else "Your turn"
    w = _winner_side(ch)
    if w == "tie":
        return "Tie"
    if w == "challenger":
        return "You won" if as_challenger else "You lost"
    if w == "opponent":
        return "You lost" if as_challenger else "You won"
    return "Complete"


def _pick_question_ids(category: str) -> list[int] | None:
    rows = (
        Question.query.filter_by(category=category, is_approved=True)
        .order_by(db.func.random())
        .limit(TOTAL_CHALLENGE_Q)
        .all()
    )
    if len(rows) < TOTAL_CHALLENGE_Q:
        return None
    return [q.id for q in rows]


def _answered_ids(challenge_id: int, user_id: int) -> set[int]:
    rows = ChallengeAnswer.query.filter_by(challenge_id=challenge_id, user_id=user_id).all()
    return {r.question_id for r in rows}


def _next_question(challenge: Challenge, user_id: int) -> Question | None:
    answered = _answered_ids(challenge.id, user_id)
    for qid in challenge.question_ids:
        if qid not in answered:
            return db.session.get(Question, qid)
    return None


def _finalize_side(challenge: Challenge, user_id: int, *, is_challenger: bool) -> None:
    rows = ChallengeAnswer.query.filter_by(challenge_id=challenge.id, user_id=user_id).all()
    score = sum(r.points_earned for r in rows)
    correct = sum(1 for r in rows if r.correct)
    time_ms = sum(r.response_time_ms for r in rows)
    now = datetime.utcnow()
    if is_challenger:
        challenge.challenger_score = score
        challenge.challenger_correct_count = correct
        challenge.challenger_time_ms = time_ms
        challenge.challenger_completed_at = now
        challenge.status = "active"
    else:
        challenge.opponent_score = score
        challenge.opponent_correct_count = correct
        challenge.opponent_time_ms = time_ms
        challenge.opponent_completed_at = now
        challenge.status = "complete"


def _participant_role(challenge: Challenge, user_id: int) -> str | None:
    if challenge.challenger_id == user_id:
        return "challenger"
    if challenge.opponent_id == user_id:
        return "opponent"
    return None


@challenge_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if not current_user.is_premium:
        if request.method == "POST":
            flash("Creating challenges is a Premium feature.", "error")
        return render_template("challenge_upsell.html")

    if request.method == "POST":
        cat = (request.form.get("category") or "").strip().lower()
        opponent_name = (request.form.get("opponent_username") or "").strip()
        if cat not in CATEGORIES:
            flash("Pick a valid category.", "error")
            return redirect(url_for("challenge.create"))
        if not opponent_name:
            flash("Enter your friend's username.", "error")
            return redirect(url_for("challenge.create"))
        opponent = User.query.filter_by(username=opponent_name).first()
        if not opponent:
            flash("No user found with that username.", "error")
            return redirect(url_for("challenge.create"))
        if opponent.id == current_user.id:
            flash("You can't challenge yourself.", "error")
            return redirect(url_for("challenge.create"))

        qids = _pick_question_ids(cat)
        if not qids:
            flash("Not enough approved questions in that category yet. Try another category.", "error")
            return redirect(url_for("challenge.create"))

        ch = Challenge(
            challenger_id=current_user.id,
            opponent_id=opponent.id,
            category=cat,
            question_ids=qids,
            status="pending",
        )
        db.session.add(ch)
        db.session.commit()
        return redirect(url_for("challenge.play", challenge_id=ch.id))

    return render_template("challenge_create.html", categories=CATEGORIES)


@challenge_bp.route("/challenges")
@login_required
def challenges_list():
    sent = (
        Challenge.query.filter_by(challenger_id=current_user.id)
        .order_by(Challenge.created_at.desc())
        .all()
    )
    received = (
        Challenge.query.filter_by(opponent_id=current_user.id)
        .order_by(Challenge.created_at.desc())
        .all()
    )
    sent_rows = [(c, _history_label(c, True)) for c in sent]
    recv_rows = [(c, _history_label(c, False)) for c in received]
    return render_template("challenge_list.html", sent_rows=sent_rows, recv_rows=recv_rows)


@challenge_bp.route("/<int:challenge_id>")
@login_required
def detail(challenge_id):
    ch = db.session.get(Challenge, challenge_id)
    if not ch:
        abort(404)
    role = _participant_role(ch, current_user.id)
    if not role:
        abort(404)

    # Opponent must not see challenger's score until the challenge is complete.
    hide_challenger_score = role == "opponent" and ch.status != "complete"

    share_url = url_for("challenge.detail", challenge_id=ch.id, _external=True)

    def _acc(correct: int | None) -> float | None:
        if correct is None:
            return None
        return round(100.0 * correct / TOTAL_CHALLENGE_Q, 1)

    winner_side = _winner_side(ch)

    opponent_progress = 0
    if role == "opponent":
        opponent_progress = ChallengeAnswer.query.filter_by(
            challenge_id=ch.id, user_id=current_user.id
        ).count()

    return render_template(
        "challenge_detail.html",
        challenge=ch,
        role=role,
        share_url=share_url,
        hide_challenger_score=hide_challenger_score,
        show_results=(ch.status == "complete"),
        acc_ch=_acc(ch.challenger_correct_count),
        acc_op=_acc(ch.opponent_correct_count),
        total_q=TOTAL_CHALLENGE_Q,
        winner_side=winner_side,
        opponent_progress=opponent_progress,
    )


@challenge_bp.route("/<int:challenge_id>/accept", methods=["POST"])
@login_required
def accept(challenge_id):
    ch = db.session.get(Challenge, challenge_id)
    if not ch or ch.opponent_id != current_user.id:
        abort(404)
    if not ch.challenger_completed_at:
        flash("The challenger has not finished yet.", "error")
        return redirect(url_for("challenge.detail", challenge_id=ch.id))
    if ch.opponent_completed_at:
        return redirect(url_for("challenge.detail", challenge_id=ch.id))
    return redirect(url_for("challenge.play", challenge_id=ch.id))


@challenge_bp.route("/<int:challenge_id>/play")
@login_required
def play(challenge_id):
    ch = db.session.get(Challenge, challenge_id)
    if not ch:
        abort(404)
    role = _participant_role(ch, current_user.id)
    if not role:
        abort(404)

    if role == "challenger":
        if ch.challenger_completed_at:
            return redirect(url_for("challenge.detail", challenge_id=ch.id))
    else:
        if not ch.challenger_completed_at:
            flash("Wait until the challenger finishes their run.", "error")
            return redirect(url_for("challenge.detail", challenge_id=ch.id))
        if ch.opponent_completed_at:
            return redirect(url_for("challenge.detail", challenge_id=ch.id))

    q = _next_question(ch, current_user.id)
    if not q:
        return redirect(url_for("challenge.detail", challenge_id=ch.id))

    answered = _answered_ids(ch.id, current_user.id)
    question_number = len(answered) + 1
    return render_template(
        "challenge_play.html",
        challenge=ch,
        question=q,
        question_number=question_number,
        total=TOTAL_CHALLENGE_Q,
    )


@challenge_bp.route("/<int:challenge_id>/answer_json", methods=["POST"])
@login_required
def answer_json(challenge_id):
    ch = db.session.get(Challenge, challenge_id)
    if not ch:
        abort(404)
    role = _participant_role(ch, current_user.id)
    if not role:
        abort(403)

    if role == "challenger" and ch.challenger_completed_at:
        return jsonify({"redirect_url": url_for("challenge.detail", challenge_id=ch.id)}), 200
    if role == "opponent":
        if not ch.challenger_completed_at:
            abort(400)
        if ch.opponent_completed_at:
            return jsonify({"redirect_url": url_for("challenge.detail", challenge_id=ch.id)}), 200

    question_id = request.form.get("question_id", type=int)
    answer_val = request.form.get("answer")
    response_time_ms = request.form.get("response_time_ms", type=int, default=15000)

    if question_id not in ch.question_ids:
        abort(400)
    if ChallengeAnswer.query.filter_by(
        challenge_id=ch.id, user_id=current_user.id, question_id=question_id
    ).first():
        return jsonify({"redirect_url": url_for("challenge.play", challenge_id=ch.id)}), 200

    question = db.session.get(Question, question_id)
    if not question:
        abort(404)
    if answer_val not in ("ai", "real", "timeout"):
        abort(400)

    response_time_ms = max(0, min(15000, response_time_ms))
    if answer_val == "timeout":
        user_answer = None
        correct = False
    else:
        user_answer = answer_val == "ai"
        correct = user_answer != question.is_real

    points = calculate_points(correct, response_time_ms)
    row = ChallengeAnswer(
        challenge_id=ch.id,
        user_id=current_user.id,
        question_id=question_id,
        answer=user_answer,
        correct=correct,
        response_time_ms=response_time_ms,
        points_earned=points,
    )
    db.session.add(row)
    db.session.flush()

    answered = _answered_ids(ch.id, current_user.id)
    finished = len(answered) >= TOTAL_CHALLENGE_Q
    if finished:
        _finalize_side(ch, current_user.id, is_challenger=(role == "challenger"))

    db.session.commit()

    correct_answer = "real" if question.is_real else "ai"
    explanation = explanation_for(question)
    if finished:
        next_url = url_for("challenge.detail", challenge_id=ch.id)
    else:
        next_url = url_for("challenge.play", challenge_id=ch.id)

    return jsonify(
        {
            "correct": bool(correct),
            "points": int(points),
            "correct_answer": correct_answer,
            "explanation": explanation,
            "next_url": next_url,
        }
    ), 200


@challenge_bp.route("/<int:challenge_id>/answer", methods=["POST"])
@login_required
def answer_fallback(challenge_id):
    """Non-JS fallback: single-step redirect without flip."""
    ch = db.session.get(Challenge, challenge_id)
    if not ch:
        abort(404)
    role = _participant_role(ch, current_user.id)
    if not role:
        abort(403)
    if role == "challenger" and ch.challenger_completed_at:
        return redirect(url_for("challenge.detail", challenge_id=ch.id))
    if role == "opponent":
        if not ch.challenger_completed_at:
            abort(400)
        if ch.opponent_completed_at:
            return redirect(url_for("challenge.detail", challenge_id=ch.id))

    question_id = request.form.get("question_id", type=int)
    answer_val = request.form.get("answer")
    response_time_ms = request.form.get("response_time_ms", type=int, default=15000)

    if question_id not in ch.question_ids:
        abort(400)
    if ChallengeAnswer.query.filter_by(
        challenge_id=ch.id, user_id=current_user.id, question_id=question_id
    ).first():
        return redirect(url_for("challenge.play", challenge_id=ch.id))

    question = db.session.get(Question, question_id)
    if not question or answer_val not in ("ai", "real", "timeout"):
        abort(400)

    response_time_ms = max(0, min(15000, response_time_ms))
    if answer_val == "timeout":
        user_answer = None
        correct = False
    else:
        user_answer = answer_val == "ai"
        correct = user_answer != question.is_real
    points = calculate_points(correct, response_time_ms)
    db.session.add(
        ChallengeAnswer(
            challenge_id=ch.id,
            user_id=current_user.id,
            question_id=question_id,
            answer=user_answer,
            correct=correct,
            response_time_ms=response_time_ms,
            points_earned=points,
        )
    )
    db.session.flush()
    answered = _answered_ids(ch.id, current_user.id)
    if len(answered) >= TOTAL_CHALLENGE_Q:
        _finalize_side(ch, current_user.id, is_challenger=(role == "challenger"))
    db.session.commit()
    return redirect(url_for("challenge.play", challenge_id=ch.id))
