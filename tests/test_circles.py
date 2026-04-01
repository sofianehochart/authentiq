def test_create_circle(logged_in_client, app):
    r = logged_in_client.post('/circles/create', data={'name': 'Yale Squad'}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from models import Circle
        c = Circle.query.filter_by(name='Yale Squad').first()
        assert c is not None
        assert len(c.invite_code) == 6


def test_join_circle_with_valid_code(logged_in_client, app):
    # Create a circle first with a second user
    with app.app_context():
        from models import Circle, CircleMember, User
        from extensions import db
        from werkzeug.security import generate_password_hash
        owner = User(username='owner', avatar_colour='#7c3aed',
                     password_hash=generate_password_hash('p'))
        db.session.add(owner)
        db.session.commit()
        circle = Circle(name='Test Circle', invite_code='ABC123', creator_id=owner.id)
        db.session.add(circle)
        db.session.commit()

    r = logged_in_client.post('/circles/join', data={'invite_code': 'ABC123'}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from models import CircleMember, User, Circle
        user = User.query.filter_by(username='testuser').first()
        circle = Circle.query.filter_by(invite_code='ABC123').first()
        membership = CircleMember.query.filter_by(user_id=user.id, circle_id=circle.id).first()
        assert membership is not None


def test_join_invalid_code_shows_error(logged_in_client):
    r = logged_in_client.post('/circles/join', data={'invite_code': 'BADXXX'}, follow_redirects=True)
    assert b'not found' in r.data.lower() or b'invalid' in r.data.lower()


def test_leave_circle(logged_in_client, app):
    with app.app_context():
        from models import Circle, CircleMember, User
        from extensions import db
        user = User.query.filter_by(username='testuser').first()
        circle = Circle(name='Temp', invite_code='TEMP99', creator_id=user.id)
        db.session.add(circle)
        db.session.commit()
        membership = CircleMember(user_id=user.id, circle_id=circle.id)
        db.session.add(membership)
        db.session.commit()
    r = logged_in_client.post('/circles/leave', follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from models import CircleMember, User
        user = User.query.filter_by(username='testuser').first()
        assert CircleMember.query.filter_by(user_id=user.id).count() == 0
