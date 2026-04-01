import os
from flask import Flask
from extensions import db, login_manager


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-change-me'),
        SQLALCHEMY_DATABASE_URI='sqlite:///authentiq.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return db.session.get(User, int(user_id))

    from routes.auth import auth_bp
    from routes.quiz import quiz_bp
    from routes.circles import circles_bp
    from routes.leaderboard import leaderboard_bp
    from routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(circles_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(profile_bp)

    with app.app_context():
        db.create_all()
        _seed_questions_if_empty()

    return app


def _seed_questions_if_empty():
    try:
        from models import Question
        if Question.query.count() == 0:
            import json
            from pathlib import Path
            path = Path(__file__).parent / 'data' / 'questions.json'
            if path.exists():
                with open(path) as f:
                    for q in json.load(f):
                        db.session.add(Question(**q))
                db.session.commit()
    except ImportError:
        pass  # models.py not yet populated — Task 2 adds the models


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
