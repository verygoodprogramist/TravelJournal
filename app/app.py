from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from datetime import datetime
from flask_babel import Babel
from flask_babel import _


# Завантаження змінних середовища
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or 'supersecretkey'

# Шлях до бази даних
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tv.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATIONS_DERECTORIES'] = 'app/translations'  # English, Ukrainian

# Абсолютний шлях до папки static/uploads
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, 'static', 'uploads')

db = SQLAlchemy(app)


# Моделі
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    notes = db.relationship('Note', backref='author', lazy=True)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

# Роути
def get_locale():
    return session.get('lang', 'en')

babel = Babel(app)
babel.init_app(app, locale_selector=get_locale)

@app.route('/set_language/<lang>')
def set_language(lang):
    session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User already exists.')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registered successfully.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', notes=user.notes)

@app.route('/add_note', methods=['GET', 'POST'])
def add_note():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        file = request.files.get('image')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if latitude and longitude:
            latitude = float(latitude)
            longitude = float(longitude)
        else:
            latitude = None
            longitude = None
        
        image_path = None
        if file and file.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            image_path = os.path.relpath(filepath, os.path.join(app.root_path, 'static')).replace("\\", "/")

        new_note = Note(
            title=title,
            content=content,
            image_path=image_path,
            user_id=session['user_id'],
            latitude=latitude,
            longitude=longitude
        )
        db.session.add(new_note)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('add_note.html')

@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    note = Note.query.get_or_404(note_id)
    if note.user_id != session['user_id']:
        flash('Access denied.')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        note.title = request.form['title']
        note.content = request.form['content']

        # Handle optional image replacement
        file = request.files.get('image')
        if file and file.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            note.image_path = os.path.relpath(filepath, os.path.join(app.root_path, 'static')).replace("\\", "/")

        # Handle optional new coordinates
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')

        if lat and lng:
            note.latitude = float(lat)
            note.longitude = float(lng)

        db.session.commit()
        flash('Note updated.')
        return redirect(url_for('dashboard'))

    return render_template('edit_note.html', note=note)


@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    note = Note.query.get_or_404(note_id)
    if note.user_id != session['user_id']:
        flash('Access denied.')
        return redirect(url_for('dashboard'))
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('dashboard'))

# Ініціалізація
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
