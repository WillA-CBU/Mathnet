from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from flask_login import LoginManager

db = SQLAlchemy()
DB_NAME = "database.db"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'willssecretkey'

    # Get the absolute path of the directory where this file is located
    base_dir = os.path.abspath(os.path.dirname(__file__))
    # Construct the full path for the database file within the application's directory
    db_path = os.path.join(base_dir, DB_NAME)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path

    db.init_app(app)

    from .routes import routes
    from .auth import auth

    app.register_blueprint(routes, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import Course, User

    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app
