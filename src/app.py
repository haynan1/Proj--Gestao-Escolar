import logging
import os
import sys
from datetime import timedelta
from urllib.parse import urlsplit

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

sys.path.insert(0, SRC_DIR)

from flask import Flask, send_from_directory, url_for
from dotenv import load_dotenv
from auth import csrf_protect
from database.schema import create_tables
from extensions import limiter
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
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
_secret_key = os.getenv('FLASK_SECRET_KEY', '').strip()
_WEAK_KEYS = {'', 'change_this_secret_key', 'dev-secret-change-me'}
if _secret_key in _WEAK_KEYS:
    logging.getLogger(__name__).warning(
        'FLASK_SECRET_KEY nao configurada ou usa valor padrao inseguro. '
        'Defina uma chave forte no .env antes do deploy em producao.'
    )
    if not _secret_key:
        _secret_key = 'dev-only-insecure-fallback'
app.secret_key = _secret_key

_session_lifetime_hours = int(os.getenv('SESSION_LIFETIME_HOURS', '8'))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=_get_bool_env('SESSION_COOKIE_SECURE', default=False),
    REMEMBER_COOKIE_SECURE=_get_bool_env('SESSION_COOKIE_SECURE', default=False),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=_session_lifetime_hours),
    VERIFY_EMAIL_TOKEN_MAX_AGE=int(os.getenv('VERIFY_EMAIL_TOKEN_MAX_AGE', str(60 * 60 * 24))),
    RESET_PASSWORD_TOKEN_MAX_AGE=int(os.getenv('RESET_PASSWORD_TOKEN_MAX_AGE', str(60 * 60))),
    APP_BASE_URL=os.getenv('APP_BASE_URL', '').strip(),
)

app_base_url = app.config.get('APP_BASE_URL', '')
if app_base_url:
    parsed_base_url = urlsplit(app_base_url)
    if parsed_base_url.scheme:
        app.config['PREFERRED_URL_SCHEME'] = parsed_base_url.scheme

limiter.init_app(app)
app.before_request(csrf_protect)


@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return response


@app.context_processor
def inject_static_url():
    def static_url(filename):
        static_path = os.path.join(app.static_folder, filename)
        try:
            version = int(os.path.getmtime(static_path))
        except OSError:
            version = int(os.path.getmtime(__file__))
        return url_for('static', filename=filename, v=version)

    return {'static_url': static_url}


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.static_folder, 'favicon'),
        'imagem1.ico',
        mimetype='image/vnd.microsoft.icon',
    )

# Registra blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(escola_bp)
app.register_blueprint(dashboard_bp)
create_tables()


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    debug = _get_bool_env('FLASK_DEBUG', default=False)

    _startup_log = logging.getLogger(__name__)
    _startup_log.info("Flowter iniciando em http://localhost:%d (debug=%s)", port, debug)
    app.run(debug=debug, host='0.0.0.0', port=port)
