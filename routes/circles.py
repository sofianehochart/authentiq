import random
import string
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Circle, CircleMember

circles_bp = Blueprint('circles', __name__)


def _generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _get_user_circle():
    membership = CircleMember.query.filter_by(user_id=current_user.id).first()
    if membership:
        return db.session.get(Circle, membership.circle_id)
    return None


@circles_bp.route('/circles')
@login_required
def circles():
    circle = _get_user_circle()
    return render_template('circles.html', circle=circle)


@circles_bp.route('/circles/create', methods=['POST'])
@login_required
def create():
    if CircleMember.query.filter_by(user_id=current_user.id).first():
        flash('You are already in a Circle. Leave it first.', 'error')
        return redirect(url_for('circles.circles'))
    name = request.form.get('name', '').strip()
    if not name:
        flash('Circle name is required.', 'error')
        return redirect(url_for('circles.circles'))
    code = _generate_code()
    while Circle.query.filter_by(invite_code=code).first():
        code = _generate_code()
    circle = Circle(name=name, invite_code=code, creator_id=current_user.id)
    db.session.add(circle)
    db.session.flush()
    db.session.add(CircleMember(user_id=current_user.id, circle_id=circle.id))
    db.session.commit()
    flash(f'Circle created! Invite code: {code}', 'success')
    return redirect(url_for('circles.circles'))


@circles_bp.route('/circles/join', methods=['POST'])
@login_required
def join():
    if CircleMember.query.filter_by(user_id=current_user.id).first():
        flash('You are already in a Circle. Leave it first.', 'error')
        return redirect(url_for('circles.circles'))
    code = request.form.get('invite_code', '').strip().upper()
    circle = Circle.query.filter_by(invite_code=code).first()
    if not circle:
        flash('Circle not found. Check the code and try again.', 'error')
        return redirect(url_for('circles.circles'))
    db.session.add(CircleMember(user_id=current_user.id, circle_id=circle.id))
    db.session.commit()
    flash(f'Joined {circle.name}!', 'success')
    return redirect(url_for('circles.circles'))


@circles_bp.route('/circles/leave', methods=['POST'])
@login_required
def leave():
    membership = CircleMember.query.filter_by(user_id=current_user.id).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash('You have left the Circle.', 'success')
    return redirect(url_for('circles.circles'))
