from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import case, func

from extensions import db
from models import GameSession, Question, QuestionResult

stats_bp = Blueprint("stats", __name__)

CATEGORIES = ("sports", "politics", "celebrity")
FORMATS = ("tweet", "instagram", "audio")
MIN_CELL_N = 3


def _pct(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * correct / total, 1)


def _streaks(played_dates: set[date]) -> tuple[int, int]:
    """Consecutive-day streak ending today, and longest ever streak."""
    if not played_dates:
        return 0, 0

    longest = 0
    sorted_days = sorted(played_dates)
    run = 0
    prev: date | None = None
    for d in sorted_days:
        if prev is None or d == prev + timedelta(days=1):
            run += 1
        else:
            longest = max(longest, run)
            run = 1
        prev = d
    longest = max(longest, run)

    current = 0
    d = date.today()
    while d in played_dates:
        current += 1
        d -= timedelta(days=1)

    return current, longest


def _bucket_format(fmt: str) -> str | None:
    f = (fmt or "").strip().lower()
    if f in FORMATS:
        return f
    return None


def _bucket_category(cat: str) -> str | None:
    c = (cat or "").strip().lower()
    if c in CATEGORIES:
        return c
    return None


@stats_bp.route("/stats")
@login_required
def stats_page():
    uid = current_user.id

    base = (
        db.session.query(QuestionResult, Question)
        .join(Question, Question.id == QuestionResult.question_id)
        .join(GameSession, GameSession.id == QuestionResult.session_id)
        .filter(GameSession.user_id == uid)
    )

    totals_row = base.with_entities(
        func.count(QuestionResult.id),
        func.sum(case((QuestionResult.is_correct.is_(True), 1), else_=0)),
        func.avg(QuestionResult.response_time_ms),
    ).one()

    total_n = int(totals_row[0] or 0)
    total_correct = int(totals_row[1] or 0)
    avg_ms = totals_row[2]
    overall_acc = _pct(total_correct, total_n)
    avg_response_ms = int(round(float(avg_ms))) if avg_ms is not None and total_n else None

    completed_days_rows = (
        db.session.query(GameSession.completed_at)
        .filter(GameSession.user_id == uid, GameSession.completed_at.isnot(None))
        .all()
    )
    played_dates = {r[0].date() for r in completed_days_rows if r[0]}
    current_streak, longest_streak = _streaks(played_dates)

    # By format
    fmt_rows = (
        db.session.query(
            Question.format,
            func.count(QuestionResult.id),
            func.sum(case((QuestionResult.is_correct.is_(True), 1), else_=0)),
        )
        .select_from(QuestionResult)
        .join(Question, Question.id == QuestionResult.question_id)
        .join(GameSession, GameSession.id == QuestionResult.session_id)
        .filter(GameSession.user_id == uid)
        .group_by(Question.format)
        .all()
    )
    by_format: dict[str, dict[str, Any]] = {
        f: {"n": 0, "correct": 0, "acc": 0.0} for f in FORMATS
    }
    for fmt, n, c in fmt_rows:
        key = _bucket_format(str(fmt))
        if not key:
            continue
        n = int(n or 0)
        c = int(c or 0)
        by_format[key]["n"] += n
        by_format[key]["correct"] += c
    for f in FORMATS:
        bf = by_format[f]
        bf["acc"] = _pct(bf["correct"], bf["n"])

    # By category
    cat_rows = (
        db.session.query(
            Question.category,
            func.count(QuestionResult.id),
            func.sum(case((QuestionResult.is_correct.is_(True), 1), else_=0)),
        )
        .select_from(QuestionResult)
        .join(Question, Question.id == QuestionResult.question_id)
        .join(GameSession, GameSession.id == QuestionResult.session_id)
        .filter(GameSession.user_id == uid)
        .group_by(Question.category)
        .all()
    )
    by_category: dict[str, dict[str, Any]] = {
        c: {"n": 0, "correct": 0, "acc": 0.0} for c in CATEGORIES
    }
    for cat, n, corr in cat_rows:
        key = _bucket_category(str(cat))
        if not key:
            continue
        n = int(n or 0)
        corr = int(corr or 0)
        by_category[key]["n"] += n
        by_category[key]["correct"] += corr
    for c in CATEGORIES:
        bc = by_category[c]
        bc["acc"] = _pct(bc["correct"], bc["n"])

    # Grid category x format
    grid_rows = (
        db.session.query(
            Question.category,
            Question.format,
            func.count(QuestionResult.id),
            func.sum(case((QuestionResult.is_correct.is_(True), 1), else_=0)),
        )
        .select_from(QuestionResult)
        .join(Question, Question.id == QuestionResult.question_id)
        .join(GameSession, GameSession.id == QuestionResult.session_id)
        .filter(GameSession.user_id == uid)
        .group_by(Question.category, Question.format)
        .all()
    )
    grid: dict[tuple[str, str], dict[str, Any]] = {}
    for cat, fmt, n, corr in grid_rows:
        ck = _bucket_category(str(cat))
        fk = _bucket_format(str(fmt))
        if not ck or not fk:
            continue
        n = int(n or 0)
        corr = int(corr or 0)
        grid[(ck, fk)] = {"n": n, "correct": corr}

    grid_cells: list[list[dict[str, Any]]] = []
    for c in CATEGORIES:
        row: list[dict[str, Any]] = []
        for f in FORMATS:
            cell = grid.get((c, f))
            if not cell or cell["n"] < MIN_CELL_N:
                row.append({"label": "-", "n": cell["n"] if cell else 0, "acc": None})
            else:
                row.append({"label": f"{_pct(cell['correct'], cell['n'])}%", "n": cell["n"], "acc": _pct(cell["correct"], cell["n"])})
        grid_cells.append(row)

    return render_template(
        "stats.html",
        total_n=total_n,
        overall_acc=overall_acc,
        avg_response_ms=avg_response_ms,
        current_streak=current_streak,
        longest_streak=longest_streak,
        by_format=by_format,
        by_category=by_category,
        grid_rows_labels=list(CATEGORIES),
        grid_cols_labels=list(FORMATS),
        grid_cells=grid_cells,
        is_premium=bool(getattr(current_user, "is_premium", False)),
    )
