def test_quiz_requires_login(client):
    r = client.get('/quiz')
    assert r.status_code == 302
    assert '/login' in r.headers['Location']


def test_quiz_shows_question(logged_in_client, sample_questions):
    r = logged_in_client.get('/quiz')
    assert r.status_code == 200
    assert b'REAL' in r.data
    assert b'AI' in r.data


def test_answer_submission_redirects(logged_in_client, sample_questions, app):
    with app.app_context():
        from models import QuizAttempt, DailySet
        from utils.daily import get_or_create_daily_set
        ds = get_or_create_daily_set()
        from extensions import db
        from models import User
        user = User.query.filter_by(username='testuser').first()
        attempt = QuizAttempt(user_id=user.id, daily_set_id=ds.id)
        db.session.add(attempt)
        db.session.commit()
        first_q_id = ds.get_question_ids()[0]
        r = logged_in_client.post('/quiz/answer', data={
            'attempt_id': attempt.id,
            'question_id': first_q_id,
            'answer': 'ai',
            'response_time_ms': 2000
        })
        assert r.status_code == 302


def test_completed_quiz_redirects_to_results(logged_in_client, sample_questions, app):
    # Play all 10 questions
    r = logged_in_client.get('/quiz')
    assert r.status_code == 200
    with app.app_context():
        from models import QuizAttempt, DailySet
        from utils.daily import get_or_create_daily_set
        from extensions import db
        from models import User
        ds = get_or_create_daily_set()
        user = User.query.filter_by(username='testuser').first()
        attempt = QuizAttempt.query.filter_by(user_id=user.id, daily_set_id=ds.id).first()
        for qid in ds.get_question_ids():
            logged_in_client.post('/quiz/answer', data={
                'attempt_id': attempt.id,
                'question_id': qid,
                'answer': 'ai',
                'response_time_ms': 5000
            })
        attempt = db.session.get(QuizAttempt, attempt.id)
        assert attempt.completed_at is not None
