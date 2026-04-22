import re

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from auth import (
    SESSION_USER_ID_KEY,
    generate_csrf_token,
    generate_signed_token,
    get_safe_redirect_target,
    login_user,
    logout_user,
    verify_signed_token,
)
from email_service import (
    notify_delivery,
    send_password_reset_email,
    send_verification_email,
)
from models.user import (
    LOCK_MINUTES,
    atualizar_senha,
    autenticar_usuario,
    buscar_usuario_por_email,
    buscar_usuario_por_id,
    criar_usuario,
    marcar_email_como_verificado,
)


EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
DEFAULT_VERIFY_TOKEN_MAX_AGE = 60 * 60 * 24
DEFAULT_RESET_TOKEN_MAX_AGE = 60 * 60


auth_bp = Blueprint('auth', __name__)


@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get(SESSION_USER_ID_KEY)
    g.user = buscar_usuario_por_id(user_id) if user_id else None
    if user_id and g.user is None:
        session.clear()


@auth_bp.app_context_processor
def inject_auth_helpers():
    return {
        'current_user': g.get('user'),
        'csrf_token': generate_csrf_token,
    }


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.get('user'):
        return redirect(get_safe_redirect_target())

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()

        if not email or not senha:
            flash('Informe e-mail e senha para entrar.', 'error')
        else:
            usuario, erro = autenticar_usuario(email, senha)
            if usuario and not erro:
                login_user(usuario)
                flash(f'Bem-vindo, {usuario["nome"]}.', 'success')
                return redirect(get_safe_redirect_target())

            if erro == 'email_not_verified' and usuario:
                _dispatch_verification_email(usuario)
                flash('Seu e-mail ainda não foi confirmado. Enviamos um novo link de verificação.', 'error')
            elif erro == 'temporarily_locked':
                flash(
                    f'Muitas tentativas inválidas. Aguarde cerca de {LOCK_MINUTES} minutos antes de tentar novamente.',
                    'error',
                )
            else:
                flash('E-mail ou senha inválidos.', 'error')

    return render_template('login.html', next_url=request.values.get('next', ''))


@auth_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if g.get('user'):
        return redirect(get_safe_redirect_target())

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()
        confirmar_senha = request.form.get('confirmar_senha', '').strip()

        if not nome or not email or not senha:
            flash('Preencha nome, e-mail e senha.', 'error')
        elif not EMAIL_PATTERN.match(email):
            flash('Informe um e-mail válido.', 'error')
        elif len(senha) < 8:
            flash('A senha precisa ter pelo menos 8 caracteres.', 'error')
        elif senha != confirmar_senha:
            flash('A confirmação de senha não confere.', 'error')
        else:
            sucesso, mensagem = criar_usuario(nome, email, senha)
            flash(mensagem, 'success' if sucesso else 'error')
            if sucesso:
                usuario = buscar_usuario_por_email(email)
                if usuario:
                    _dispatch_verification_email(usuario)
                flash('Confira seu e-mail para ativar a conta antes de entrar.', 'success')
                return redirect(url_for('auth.login'))

    return render_template('register.html', next_url=request.values.get('next', ''))


@auth_bp.route('/reenviar-verificacao', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        usuario = buscar_usuario_por_email(email) if email else None
        if usuario and not usuario.get('email_verificado'):
            _dispatch_verification_email(usuario)
        flash(
            'Se existir uma conta pendente para esse e-mail, um novo link de verificação foi enviado.',
            'success',
        )
        return redirect(url_for('auth.login'))

    return render_template('resend_verification.html')


@auth_bp.route('/verificar-email/<token>')
def verify_email(token):
    payload = verify_signed_token(
        'verify-email',
        token,
        max_age=_get_verify_token_max_age(),
    )
    if not payload:
        flash('O link de verificação é inválido ou expirou. Solicite um novo.', 'error')
        return redirect(url_for('auth.resend_verification'))

    usuario = buscar_usuario_por_id(payload.get('user_id'))
    if not usuario or usuario['email'] != payload.get('email'):
        flash('Não foi possível validar essa conta.', 'error')
        return redirect(url_for('auth.login'))

    if usuario.get('token_version') != payload.get('token_version'):
        flash('Esse link de verificação não é mais válido.', 'error')
        return redirect(url_for('auth.resend_verification'))

    if not usuario.get('email_verificado'):
        marcar_email_como_verificado(usuario['id'])

    flash('E-mail confirmado com sucesso. Agora você já pode entrar.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        usuario = buscar_usuario_por_email(email) if email else None
        if usuario:
            _dispatch_password_reset_email(usuario)
        flash(
            'Se existir uma conta com esse e-mail, você receberá instruções para redefinir a senha.',
            'success',
        )
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def reset_password(token):
    payload = verify_signed_token(
        'reset-password',
        token,
        max_age=_get_reset_token_max_age(),
    )
    if not payload:
        flash('O link de redefinição é inválido ou expirou. Solicite um novo.', 'error')
        return redirect(url_for('auth.forgot_password'))

    usuario = buscar_usuario_por_id(payload.get('user_id'))
    if not usuario or usuario['email'] != payload.get('email'):
        flash('Não foi possível validar esse pedido de redefinição.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if usuario.get('token_version') != payload.get('token_version'):
        flash('Esse link de redefinição não é mais válido.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        senha = request.form.get('senha', '').strip()
        confirmar_senha = request.form.get('confirmar_senha', '').strip()

        if len(senha) < 8:
            flash('A senha precisa ter pelo menos 8 caracteres.', 'error')
        elif senha != confirmar_senha:
            flash('A confirmação de senha não confere.', 'error')
        else:
            atualizar_senha(usuario['id'], senha, validar_email=True)
            flash('Senha atualizada com sucesso. Entre com a nova credencial.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    flash('Sessão encerrada com sucesso.', 'success')
    return redirect(url_for('auth.login'))


def _dispatch_verification_email(usuario: dict):
    token = generate_signed_token(
        'verify-email',
        {
            'user_id': usuario['id'],
            'email': usuario['email'],
            'token_version': usuario.get('token_version', 0),
        },
    )
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    channel = send_verification_email(usuario, verification_url)
    notify_delivery(channel, 'Link de verificação')


def _dispatch_password_reset_email(usuario: dict):
    token = generate_signed_token(
        'reset-password',
        {
            'user_id': usuario['id'],
            'email': usuario['email'],
            'token_version': usuario.get('token_version', 0),
        },
    )
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    channel = send_password_reset_email(usuario, reset_url)
    notify_delivery(channel, 'Link de redefinição de senha')


def _get_verify_token_max_age() -> int:
    return int(current_app.config.get('VERIFY_EMAIL_TOKEN_MAX_AGE', DEFAULT_VERIFY_TOKEN_MAX_AGE))


def _get_reset_token_max_age() -> int:
    return int(current_app.config.get('RESET_PASSWORD_TOKEN_MAX_AGE', DEFAULT_RESET_TOKEN_MAX_AGE))
