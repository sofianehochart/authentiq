import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db as _db
from models import User, Question


@pytest.fixture(scope='function')
def app():
    application = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret',
    })
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_questions(app):
    """10 questions, 2 per theme (1 AI + 1 real each)."""
    themes = ['Celebrity', 'Politics', 'Sports', 'Tech', 'Viral']
    qs = []
    for theme in themes:
        for is_ai in [True, False]:
            cat = theme.lower()
            q = Question(
                category=cat,
                format='tweet',
                persona='Sample',
                handle='@sample',
                content=f'{theme} {"AI" if is_ai else "real"} sample post',
                is_real=not is_ai,
                source_date='',
                explanation='',
                is_approved=True,
            )
            _db.session.add(q)
            qs.append(q)
    _db.session.commit()
    return qs


@pytest.fixture
def test_user(app):
    u = User(
        username='testuser',
        avatar_colour='#7c3aed',
        password_hash=generate_password_hash('pass123')
    )
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def logged_in_client(client, test_user):
    client.post('/login', data={'username': 'testuser', 'password': 'pass123'},
                follow_redirects=True)
    return client
