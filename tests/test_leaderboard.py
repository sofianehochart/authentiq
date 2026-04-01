def test_leaderboard_requires_login(client):
    r = client.get('/leaderboard')
    assert r.status_code == 302


def test_leaderboard_loads(logged_in_client, sample_questions):
    r = logged_in_client.get('/leaderboard')
    assert r.status_code == 200


def test_profile_loads(logged_in_client):
    r = logged_in_client.get('/profile')
    assert r.status_code == 200
    assert b'testuser' in r.data


def test_weekly_scores_include_completed_attempts(logged_in_client, sample_questions, app):
    with app.app_context():
        from models import QuizAttempt, User
        from utils.daily import get_or_create_daily_set
        from extensions import db
        from datetime import datetime
        ds = get_or_create_daily_set()
        user = User.query.filter_by(username='testuser').first()
        attempt = QuizAttempt(
            user_id=user.id, daily_set_id=ds.id,
            score=8500, completed_at=datetime.utcnow()
        )
        db.session.add(attempt)
        db.session.commit()
    r = logged_in_client.get('/leaderboard')
    assert b'8500' in r.data or b'8,500' in r.data
