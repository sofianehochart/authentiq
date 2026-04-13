"""Weekly tournament: ISO week (Mon–Sun), rotating categories, sync/rollover."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from extensions import db
from models import Question, Tournament

TOTAL_Q = 10
# (iso_week - 1) % 4 → category key
_ROTATION = ("sports", "politics", "celebrity", "mixed")


def iso_week_bounds(d: date) -> tuple[date, date, int, int]:
    """Monday and Sunday (inclusive) for the ISO week containing d, plus iso_year, iso_week."""
    iso_cal = d.isocalendar()
    if hasattr(iso_cal, "year"):
        iso_year, iso_week, iso_wday = iso_cal.year, iso_cal.week, iso_cal.weekday
    else:
        iso_year, iso_week, iso_wday = iso_cal[0], iso_cal[1], iso_cal[2]
    monday = d - timedelta(days=iso_wday - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday, iso_year, iso_week


def category_for_iso_week(iso_week: int) -> str:
    return _ROTATION[(iso_week - 1) % 4]


def next_iso_week(iso_year: int, iso_week: int) -> tuple[int, int]:
    """Next ISO week (handles year rollover)."""
    dec28 = date(iso_year, 12, 28)
    dc = dec28.isocalendar()
    last_week = dc.week if hasattr(dc, "week") else dc[1]
    if iso_week < last_week:
        return iso_year, iso_week + 1
    return iso_year + 1, 1


def pick_question_ids(category: str) -> list[int] | None:
    if category == "mixed":
        rows = (
            Question.query.filter_by(is_approved=True)
            .order_by(db.func.random())
            .limit(TOTAL_Q)
            .all()
        )
    else:
        rows = (
            Question.query.filter_by(category=category, is_approved=True)
            .order_by(db.func.random())
            .limit(TOTAL_Q)
            .all()
        )
    if len(rows) < TOTAL_Q:
        return None
    return [q.id for q in rows]


def week_end_datetime_utc(week_end: date) -> datetime:
    """Naive UTC end of Sunday (23:59:59.999999)."""
    return datetime.combine(week_end, time(23, 59, 59, 999999))


def sync_weekly_tournaments() -> Tournament | None:
    """
    Mark expired active tournaments complete.
    Ensure a row exists for the current ISO week with status 'active' and question_ids set.
    Returns the current active tournament (may be newly created).
    """
    today = date.today()

    expired = Tournament.query.filter(
        Tournament.status == "active",
        Tournament.week_end < today,
    ).all()
    for t in expired:
        t.status = "complete"

    mon, sun, _iy, iw = iso_week_bounds(today)
    cat = category_for_iso_week(iw)

    current = Tournament.query.filter(
        Tournament.week_start == mon,
        Tournament.week_end == sun,
    ).first()

    if current is None:
        qids = pick_question_ids(cat)
        if not qids:
            db.session.flush()
            return None
        current = Tournament(
            category=cat,
            week_start=mon,
            week_end=sun,
            status="active",
            question_ids=qids,
        )
        db.session.add(current)
    else:
        if current.status != "active" and current.week_end >= today:
            current.status = "active"
        if not current.question_ids:
            qids = pick_question_ids(current.category)
            if qids:
                current.question_ids = qids

    db.session.flush()
    return current


def upcoming_week_preview() -> dict[str, Any]:
    """Next ISO week after today’s week: bounds + category label."""
    mon, sun, iy, iw = iso_week_bounds(date.today())
    ny, nw = next_iso_week(iy, iw)
    n_mon = mon + timedelta(days=7)
    n_sun = sun + timedelta(days=7)
    cat = category_for_iso_week(nw)
    return {
        "week_start": n_mon,
        "week_end": n_sun,
        "iso_year": ny,
        "iso_week": nw,
        "category": cat,
        "category_label": cat.title() if cat != "mixed" else "Mixed",
    }


def entry_rank_sort_key(entry) -> tuple:
    """Higher score first, higher accuracy first, lower time first."""
    acc = entry.accuracy if entry.accuracy is not None else -1.0
    tm = entry.time_ms if entry.time_ms is not None else 10**15
    return (-entry.score, -acc, tm)


def rank_completed_entries(entries: list) -> list:
    """Return entries sorted best-first (only completed)."""
    done = [e for e in entries if e.completed_at is not None]
    return sorted(done, key=entry_rank_sort_key)


def rank_for_user(tournament_id: int, user_id: int) -> int | None:
    from models import TournamentEntry

    entries = TournamentEntry.query.filter_by(tournament_id=tournament_id).all()
    ranked = rank_completed_entries(entries)
    for i, e in enumerate(ranked, start=1):
        if e.user_id == user_id:
            return i
    return None


def best_finish_for_user(user_id: int) -> dict[str, Any] | None:
    """Best (lowest) rank across all completed tournament entries for this user."""
    from models import TournamentEntry

    entries = (
        TournamentEntry.query.filter_by(user_id=user_id)
        .filter(TournamentEntry.completed_at.isnot(None))
        .all()
    )
    if not entries:
        return None
    best_rank = 10**9
    best_meta = None
    for e in entries:
        r = rank_for_user(e.tournament_id, user_id)
        if r is not None and r < best_rank:
            best_rank = r
            best_meta = {
                "rank": r,
                "tournament_id": e.tournament_id,
                "score": e.score,
                "category": e.tournament.category if e.tournament else "",
            }
    return best_meta
