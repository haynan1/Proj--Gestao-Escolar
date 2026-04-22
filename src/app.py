import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# Garante que o diretório src está no path
sys.path.insert(0, SRC_DIR)

from flask import Flask
from dotenv import load_dotenv
from auth import csrf_protect
from database.schema import create_tables
from routes.auth_routes import auth_bp
from routes.escola_routes import escola_bp
from routes.dashboard_routes import dashboard_bp

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static',
)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=_get_bool_env('SESSION_COOKIE_SECURE', default=False),
    REMEMBER_COOKIE_SECURE=_get_bool_env('SESSION_COOKIE_SECURE', default=False),
    VERIFY_EMAIL_TOKEN_MAX_AGE=int(os.getenv('VERIFY_EMAIL_TOKEN_MAX_AGE', str(60 * 60 * 24))),
    RESET_PASSWORD_TOKEN_MAX_AGE=int(os.getenv('RESET_PASSWORD_TOKEN_MAX_AGE', str(60 * 60))),
)
app.before_request(csrf_protect)

# Registra blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(escola_bp)
app.register_blueprint(dashboard_bp)
create_tables()


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    debug = _get_bool_env('FLASK_DEBUG', default=True)

    print("=" * 50)
    print("  Sistema de Horários Escolares")
    print(f"  Acesse: http://localhost:{port}")
    print("=" * 50)
    app.run(debug=debug, host='0.0.0.0', port=port)
