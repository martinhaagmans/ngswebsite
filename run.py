from app import app

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(['xls', 'xlsx'])

app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if __name__ == '__main__':

    app.run(debug=True)
