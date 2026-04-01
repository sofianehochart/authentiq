def test_signup_creates_user(client, app):
    r = client.post('/signup', data={
        'username': 'alice', 'password': 'pass123', 'avatar_colour': '#7c3aed'
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from models import User
        assert User.query.filter_by(username='alice').first() is not None


def test_duplicate_username_rejected(client):
    client.post('/signup', data={'username': 'bob', 'password': 'pass123', 'avatar_colour': '#7c3aed'})
    r = client.post('/signup', data={'username': 'bob', 'password': 'pass456', 'avatar_colour': '#0ea5e9'},
                    follow_redirects=True)
    assert b'taken' in r.data.lower()


def test_login_correct_credentials(client):
    client.post('/signup', data={'username': 'carol', 'password': 'correct', 'avatar_colour': '#7c3aed'})
    r = client.post('/login', data={'username': 'carol', 'password': 'correct'}, follow_redirects=True)
    assert r.status_code == 200
    assert b'carol' in r.data.lower() or b'home' in r.data.lower()


def test_login_wrong_password(client):
    client.post('/signup', data={'username': 'dan', 'password': 'correct', 'avatar_colour': '#7c3aed'})
    r = client.post('/login', data={'username': 'dan', 'password': 'wrong'}, follow_redirects=True)
    assert b'invalid' in r.data.lower() or b'incorrect' in r.data.lower()


def test_logout_redirects_to_landing(logged_in_client):
    r = logged_in_client.get('/logout', follow_redirects=True)
    assert r.status_code == 200
    assert b'sign up' in r.data.lower() or b'log in' in r.data.lower()
