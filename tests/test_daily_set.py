from utils.daily import get_or_create_daily_set


def test_daily_set_creates_10_questions(app, sample_questions):
    with app.app_context():
        ds = get_or_create_daily_set()
        assert ds is not None
        assert len(ds.get_question_ids()) == 10


def test_daily_set_idempotent(app, sample_questions):
    with app.app_context():
        ds1 = get_or_create_daily_set()
        ds2 = get_or_create_daily_set()
        assert ds1.id == ds2.id


def test_daily_set_balanced_ai_real(app, sample_questions):
    with app.app_context():
        from models import Question
        ds = get_or_create_daily_set()
        ids = ds.get_question_ids()
        qs = Question.query.filter(Question.id.in_(ids)).all()
        ai_count = sum(1 for q in qs if q.is_ai)
        real_count = sum(1 for q in qs if not q.is_ai)
        # Roughly balanced: 4–6 of each
        assert 4 <= ai_count <= 6
        assert 4 <= real_count <= 6
