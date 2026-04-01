from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('quiz.home'))
    return render_template('landing.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET' and current_user.is_authenticated:
        return redirect(url_for('quiz.home'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        avatar_colour = request.form.get('avatar_colour', '#7c3aed')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('landing.html', mode='signup')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('landing.html', mode='signup')
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            avatar_colour=avatar_colour
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('quiz.home'))
    return render_template('landing.html', mode='signup')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET' and current_user.is_authenticated:
        return redirect(url_for('quiz.home'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password.', 'error')
            return render_template('landing.html', mode='login')
        login_user(user)
        return redirect(url_for('quiz.home'))
    return render_template('landing.html', mode='login')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.landing'))
