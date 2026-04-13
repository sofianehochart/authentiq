from werkzeug.security import generate_password_hash

from extensions import db
from models import Tournament, User
from utils.tournament import sync_weekly_tournaments


def test_tournaments_hub_requires_login(client):
    assert client.get("/tournaments").status_code == 302


def test_tournaments_hub_renders(logged_in_client, app, sample_questions):
    with app.app_context():
        sync_weekly_tournaments()
        db.session.commit()
    r = logged_in_client.get("/tournaments")
    assert r.status_code == 200
    assert b"Weekly tournament" in r.data


def test_tournament_play_upsell_for_free_user(logged_in_client, app, sample_questions):
    with app.app_context():
        sync_weekly_tournaments()
        db.session.commit()
        t = Tournament.query.first()
        assert t is not None
    r = logged_in_client.get(f"/tournaments/{t.id}/play")
    assert r.status_code == 200
    assert b"Premium" in r.data


def test_tournament_answer_json_forbidden_for_free_user(logged_in_client, app, sample_questions):
    with app.app_context():
        sync_weekly_tournaments()
        db.session.commit()
        t = Tournament.query.first()
        qid = t.question_ids[0]
    r = logged_in_client.post(
        f"/tournaments/{t.id}/answer_json",
        data={"question_id": qid, "answer": "real", "response_time_ms": 1000},
    )
    assert r.status_code == 403


def test_tournament_answer_json_premium_user(app, client, sample_questions):
    with app.app_context():
        u = User(
            username="prem",
            avatar_colour="#000",
            password_hash=generate_password_hash("x"),
            is_premium=True,
        )
        db.session.add(u)
        db.session.commit()
        sync_weekly_tournaments()
        db.session.commit()
        t = Tournament.query.first()
        qid = t.question_ids[0]
        tid = t.id
    client.post("/login", data={"username": "prem", "password": "x"}, follow_redirects=True)
    r = client.post(
        f"/tournaments/{tid}/answer_json",
        data={"question_id": qid, "answer": "real", "response_time_ms": 1000},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert "correct" in body
    assert "next_url" in body
