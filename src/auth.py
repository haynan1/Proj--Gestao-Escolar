import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, flash, g, jsonify, redirect, request, session, url_for
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer


SESSION_USER_ID_KEY = 'user_id'
CSRF_SESSION_KEY = '_csrf_token'
SAFE_HTTP_METHODS = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}


def login_user(user: dict) -> None:
    session.clear()
    session[SESSION_USER_ID_KEY] = user['id']
    session.permanent = True
    generate_csrf_token()


def logout_user() -> None:
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get('user') is None:
            flash('Faça login para acessar o sistema.', 'error')
            return redirect(url_for('auth.login', next=request.full_path))
        return view(*args, **kwargs)

    return wrapped_view


def get_safe_redirect_target(default_endpoint: str = 'escola.home') -> str:
    next_url = request.values.get('next', '').strip()
    if next_url and _is_safe_redirect_target(next_url):
        return next_url
    return url_for(default_endpoint)


def generate_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_protect():
    if request.method in SAFE_HTTP_METHODS:
        return None
    if request.endpoint == 'static':
        return None

    session_token = session.get(CSRF_SESSION_KEY)
    request_token = request.headers.get('X-CSRF-Token') or request.form.get('_csrf_token')

    if session_token and request_token and secrets.compare_digest(session_token, request_token):
        return None

    message = 'Sua sessão de segurança expirou. Recarregue a página e tente novamente.'
    if request.is_json:
        response = jsonify({
            'status': 'erro',
            'error': {
                'code': 'csrf_invalid',
                'message': message,
            },
        })
        response.status_code = 400
        return response

    flash(message, 'error')
    target = request.referrer or url_for('auth.login')
    return redirect(target)


def generate_signed_token(purpose: str, payload: dict) -> str:
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    return serializer.dumps(payload, salt=f'auth:{purpose}')


def verify_signed_token(purpose: str, token: str, max_age: int):
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    try:
        return serializer.loads(token, salt=f'auth:{purpose}', max_age=max_age)
    except (BadSignature, BadTimeSignature):
        return None


def _is_safe_redirect_target(target: str) -> bool:
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and target.startswith('/')
