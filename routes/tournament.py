from datetime import date, datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Question, Tournament, TournamentAnswer, TournamentEntry
from utils.scoring import calculate_points
from utils.tournament import (
    TOTAL_Q,
    iso_week_bounds,
    rank_completed_entries,
    rank_for_user,
    sync_weekly_tournaments,
    upcoming_week_preview,
    week_end_datetime_utc,
)

tournament_bp = Blueprint("tournament", __name__, url_prefix="/tournaments")


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _format_duration_ms(ms: int | None) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms} ms"
    s = ms / 1000.0
    if s < 60:
        return f"{s:.1f}s"
    m = int(s // 60)
    sec = s - m * 60
    return f"{m}m {sec:0.1f}s"


def _category_label(cat: str) -> str:
    if cat == "mixed":
        return "Mixed"
    return (cat or "").title() or "—"


def _answered_ids(tournament_id: int, user_id: int) -> set[int]:
    rows = TournamentAnswer.query.filter_by(tournament_id=tournament_id, user_id=user_id).all()
    return {r.question_id for r in rows}


def _next_question(tournament: Tournament, user_id: int) -> Question | None:
    if not tournament.question_ids:
        return None
    answered = _answered_ids(tournament.id, user_id)
    for qid in tournament.question_ids:
        if qid not in answered:
            return db.session.get(Question, qid)
    return None


def _completed_entry(tournament_id: int, user_id: int) -> TournamentEntry | None:
    row = TournamentEntry.query.filter_by(tournament_id=tournament_id, user_id=user_id).first()
    if row and row.completed_at is not None:
        return row
    return None


def _finalize_tournament_run(tournament: Tournament, user_id: int) -> TournamentEntry:
    rows = TournamentAnswer.query.filter_by(tournament_id=tournament.id, user_id=user_id).all()
    score = sum(r.points_earned for r in rows)
    correct = sum(1 for r in rows if r.correct)
    time_ms = sum(r.response_time_ms for r in rows)
    accuracy = round(100.0 * correct / TOTAL_Q, 1)
    now = datetime.utcnow()
    entry = TournamentEntry.query.filter_by(tournament_id=tournament.id, user_id=user_id).first()
    if entry is None:
        entry = TournamentEntry(
            tournament_id=tournament.id,
            user_id=user_id,
            score=score,
            accuracy=accuracy,
            time_ms=time_ms,
            completed_at=now,
        )
        db.session.add(entry)
    else:
        entry.score = score
        entry.accuracy = accuracy
        entry.time_ms = time_ms
        entry.completed_at = now
    return entry


@tournament_bp.route("")
@login_required
def hub():
    active = sync_weekly_tournaments()
    db.session.commit()

    upcoming = upcoming_week_preview()
    mon, sun, _iy, iw = iso_week_bounds(date.today())

    leaderboard_rows: list[tuple[int, TournamentEntry]] = []
    countdown_end_iso: str | None = None
    if active:
        entries = (
            TournamentEntry.query.filter_by(tournament_id=active.id)
            .filter(TournamentEntry.completed_at.isnot(None))
            .all()
        )
        ranked = rank_completed_entries(entries)
        leaderboard_rows = list(enumerate(ranked[:10], start=1))
        end_dt = week_end_datetime_utc(active.week_end)
        countdown_end_iso = end_dt.isoformat() + "Z"

    past = (
        Tournament.query.filter_by(status="complete")
        .order_by(Tournament.week_end.desc())
        .limit(12)
        .all()
    )
    past_winners: list[tuple[Tournament, TournamentEntry]] = []
    for t in past:
        ent = TournamentEntry.query.filter_by(tournament_id=t.id).filter(
            TournamentEntry.completed_at.isnot(None)
        ).all()
        ranked = rank_completed_entries(ent)
        if ranked:
            past_winners.append((t, ranked[0]))

    return render_template(
        "tournaments.html",
        active=active,
        leaderboard_rows=leaderboard_rows,
        upcoming=upcoming,
        past_winners=past_winners,
        countdown_end_iso=countdown_end_iso,
        category_label=_category_label(active.category) if active else "",
        iso_week=iw,
        week_start=mon,
        week_end=sun,
        total_q=TOTAL_Q,
        format_duration_ms=_format_duration_ms,
    )


@tournament_bp.route("/<int:tournament_id>/play")
@login_required
def play(tournament_id):
    sync_weekly_tournaments()
    db.session.commit()

    t = db.session.get(Tournament, tournament_id)
    if not t or not t.question_ids:
        abort(404)

    done = _completed_entry(t.id, current_user.id)
    if done:
        r = rank_for_user(t.id, current_user.id)
        return render_template(
            "tournament_result.html",
            tournament=t,
            entry=done,
            rank=r,
            rank_label=_ordinal(r) if r else "—",
            category_label=_category_label(t.category),
            format_duration_ms=_format_duration_ms,
        )

    if t.status == "complete":
        flash("This tournament has ended.", "error")
        return redirect(url_for("tournament.hub"))

    if not current_user.is_premium:
        return render_template(
            "tournament_upsell.html",
            tournament=t,
            category_label=_category_label(t.category),
        )

    q = _next_question(t, current_user.id)
    if not q:
        return redirect(url_for("tournament.hub"))

    answered = _answered_ids(t.id, current_user.id)
    question_number = len(answered) + 1
    return render_template(
        "tournament_play.html",
        tournament=t,
        question=q,
        question_number=question_number,
        total=TOTAL_Q,
        category_label=_category_label(t.category),
    )


@tournament_bp.route("/<int:tournament_id>/answer_json", methods=["POST"])
@login_required
def answer_json(tournament_id):
    if not current_user.is_premium:
        abort(403)

    t = db.session.get(Tournament, tournament_id)
    if not t or not t.question_ids:
        abort(404)

    if _completed_entry(t.id, current_user.id):
        return jsonify({"redirect_url": url_for("tournament.play", tournament_id=t.id)}), 200

    question_id = request.form.get("question_id", type=int)
    answer_val = request.form.get("answer")
    response_time_ms = request.form.get("response_time_ms", type=int, default=15000)

    if question_id not in t.question_ids:
        abort(400)
    if TournamentAnswer.query.filter_by(
        tournament_id=t.id, user_id=current_user.id, question_id=question_id
    ).first():
        return jsonify({"redirect_url": url_for("tournament.play", tournament_id=t.id)}), 200

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
    row = TournamentAnswer(
        tournament_id=t.id,
        user_id=current_user.id,
        question_id=question_id,
        answer=user_answer,
        correct=correct,
        response_time_ms=response_time_ms,
        points_earned=points,
    )
    db.session.add(row)
    db.session.flush()

    answered = _answered_ids(t.id, current_user.id)
    finished = len(answered) >= TOTAL_Q
    if finished:
        _finalize_tournament_run(t, current_user.id)

    db.session.commit()

    correct_answer = "real" if question.is_real else "ai"
    explanation = (question.explanation or "").strip() or "No explanation available for this question yet."
    if finished:
        next_url = url_for("tournament.play", tournament_id=t.id)
    else:
        next_url = url_for("tournament.play", tournament_id=t.id)

    return jsonify(
        {
            "correct": bool(correct),
            "points": int(points),
            "correct_answer": correct_answer,
            "explanation": explanation,
            "next_url": next_url,
        }
    ), 200


@tournament_bp.route("/<int:tournament_id>/answer", methods=["POST"])
@login_required
def answer_fallback(tournament_id):
    if not current_user.is_premium:
        abort(403)

    t = db.session.get(Tournament, tournament_id)
    if not t or not t.question_ids:
        abort(404)

    if _completed_entry(t.id, current_user.id):
        return redirect(url_for("tournament.play", tournament_id=t.id))

    question_id = request.form.get("question_id", type=int)
    answer_val = request.form.get("answer")
    response_time_ms = request.form.get("response_time_ms", type=int, default=15000)

    if question_id not in t.question_ids:
        abort(400)
    if TournamentAnswer.query.filter_by(
        tournament_id=t.id, user_id=current_user.id, question_id=question_id
    ).first():
        return redirect(url_for("tournament.play", tournament_id=t.id))

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
        TournamentAnswer(
            tournament_id=t.id,
            user_id=current_user.id,
            question_id=question_id,
            answer=user_answer,
            correct=correct,
            response_time_ms=response_time_ms,
            points_earned=points,
        )
    )
    db.session.flush()
    answered = _answered_ids(t.id, current_user.id)
    if len(answered) >= TOTAL_Q:
        _finalize_tournament_run(t, current_user.id)
    db.session.commit()
    return redirect(url_for("tournament.play", tournament_id=t.id))
