from extensions import db
from models import User


def test_premium_page_requires_login(client):
    assert client.get("/premium").status_code == 302


def test_premium_page_renders(logged_in_client):
    r = logged_in_client.get("/premium")
    assert r.status_code == 200
    assert b"AuthentIQ Premium" in r.data


def test_activate_demo_sets_premium(logged_in_client, app):
    with app.app_context():
        u = User.query.filter_by(username="testuser").first()
        assert u is not None
        assert u.is_premium is False

    r = logged_in_client.post("/premium/activate-demo", data={"next": "/home"}, follow_redirects=False)
    assert r.status_code in (301, 302)

    with app.app_context():
        u = db.session.get(User, u.id)
        assert u.is_premium is True


def test_home_premium_upsell_dismiss_session(logged_in_client):
    r = logged_in_client.get("/home")
    assert r.status_code == 200
    assert b"Unlock drills" in r.data

    r2 = logged_in_client.post("/home/dismiss-premium-upsell")
    assert r2.status_code == 204

    r3 = logged_in_client.get("/home")
    assert r3.status_code == 200
    assert b"Unlock drills" not in r3.data
