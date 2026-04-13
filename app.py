import os
from flask import Flask, redirect, url_for
from flask_login import login_required
from extensions import db, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-change-me'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///authentiq.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    import models  # noqa: F401 — register models with SQLAlchemy before migrations / seed

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return db.session.get(User, int(user_id))

    from routes.auth import auth_bp
    from routes.quiz import quiz_bp
    from routes.circles import circles_bp
    from routes.leaderboard import leaderboard_bp
    from routes.profile import profile_bp
    from routes.stats import stats_bp
    from routes.challenge import challenge_bp
    from routes.tournament import tournament_bp
    from routes.premium import premium_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(circles_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(challenge_bp)
    app.register_blueprint(tournament_bp)
    app.register_blueprint(premium_bp)

    @app.cli.command("tournaments-sync")
    def tournaments_sync_command():
        """Run weekly tournament rollover (cron: Mondays). Creates current week if missing."""
        from utils.tournament import sync_weekly_tournaments

        sync_weekly_tournaments()
        db.session.commit()

    @app.get("/challenges")
    @login_required
    def challenges_alias():
        return redirect(url_for("challenge.challenges_list"))

    with app.app_context():
        _seed_questions_if_empty()
        try:
            from utils.tournament import sync_weekly_tournaments

            sync_weekly_tournaments()
            db.session.commit()
        except Exception:
            db.session.rollback()

    return app


def _question_kwargs_from_seed_row(row: dict) -> dict:
    """Map legacy questions.json rows to the Question model."""
    author = row.get('author_label', '') or ''
    persona = (row.get('persona') or '').strip()
    if not persona:
        persona = author.lstrip('@').rstrip('_').replace('_', ' ').strip() or 'Unknown'
    handle = (row.get('handle') or author or '@unknown').strip()
    if 'is_real' in row:
        is_real = bool(row['is_real'])
    else:
        is_real = not row.get('is_ai', True)
    return {
        'category': str(row.get('category') or row.get('theme', '')).strip().lower(),
        'format': row.get('format', 'tweet'),
        'persona': persona,
        'handle': handle,
        'content': row['content'],
        'is_real': is_real,
        'source_date': str(row.get('source_date', '') or ''),
        'explanation': str(row.get('explanation', '') or ''),
        'is_approved': bool(row.get('is_approved', True)),
        'scheduled_date': row.get('scheduled_date'),
    }


def _seed_questions_if_empty():
    try:
        from sqlalchemy import inspect
        from models import Question

        if not inspect(db.engine).has_table('question'):
            return
        if Question.query.count() > 0:
            return
        import json
        from pathlib import Path
        path = Path(__file__).parent / 'data' / 'questions.json'
        if not path.exists():
            return
        with open(path, encoding='utf-8') as f:
            for row in json.load(f):
                db.session.add(Question(**_question_kwargs_from_seed_row(row)))
        db.session.commit()
    except ImportError:
        pass


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
