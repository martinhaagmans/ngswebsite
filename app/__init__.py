from flask import Flask

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(['xls', 'xlsx'])

# app.secret_key = 'super secret key'
# app.config['SESSION_TYPE'] = 'filesystem'
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

from app import views
