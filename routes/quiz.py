from flask import Blueprint, render_template
from flask_login import login_required

quiz_bp = Blueprint('quiz', __name__)


@quiz_bp.route('/home')
@login_required
def home():
    return render_template('home.html')
