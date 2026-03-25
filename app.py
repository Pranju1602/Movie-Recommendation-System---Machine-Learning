from flask import Flask
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) # Replace with a fixed secret key in production

# Register Blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)

# Auto-initialize database tables if missing
from utils.db import init_db
init_db()

if __name__ == '__main__':
    app.run(debug=True)
