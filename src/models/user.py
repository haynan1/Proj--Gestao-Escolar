from datetime import datetime, timedelta
import logging
import os

import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

from access_control import ROLE_ADMIN, ROLE_COORDINATOR, ROLE_STAFF, normalize_role
from database.connection import get_connection


MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15
MANAGED_ROLES = {ROLE_ADMIN, ROLE_COORDINATOR, ROLE_STAFF}


def criar_usuario(nome: str, email: str, senha: str, role: str = ROLE_STAFF, email_verificado: bool = False):
    conn = get_connection()
    try:
        senha_hash = generate_password_hash(senha)
        conn.execute(
            """INSERT INTO usuarios (
                   nome,
                   email,
                   senha_hash,
                   role,
                   email_verificado,
                   tentativas_login_falhas,
                   token_version
               ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (nome, email.lower(), senha_hash, normalize_role(role), bool(email_verificado), 0, 0),
        )
        conn.commit()
        return True, 'Usuario criado com sucesso.'
    except mysql.connector.Error as exc:
        conn.rollback()
        if exc.errno == 1062 and 'usuarios.email' in str(exc):
            return False, 'Ja existe um usuario cadastrado com este e-mail.'
        logging.getLogger(__name__).error('Erro ao criar usuario: %s', exc)
        return False, 'Erro interno ao criar usuario. Tente novamente.'
    except Exception:
        conn.rollback()
        logging.getLogger(__name__).exception('Erro inesperado ao criar usuario.')
        raise
    finally:
        conn.close()


def buscar_usuario_por_email(email: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE email = %s",
            (email.lower(),),
        ).fetchone()
        return _serialize_user(row)
    finally:
        conn.close()


def get_master_user_email() -> str:
    return os.getenv('AUTH_BOOTSTRAP_ADMIN_EMAIL', '').strip().lower()


def is_master_user(user: dict | None) -> bool:
    if not user:
        return False
    master_email = get_master_user_email()
    if not master_email:
        return False
    return user.get('email', '').strip().lower() == master_email


def buscar_usuario_por_id(usuario_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id = %s",
            (usuario_id,),
        ).fetchone()
        return _serialize_user(row)
    finally:
        conn.close()


def listar_usuarios(limit: int = 500):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, nome, email, role, email_verificado, ultimo_login_em, criado_em
               FROM usuarios
               ORDER BY nome, email
               LIMIT %s""",
            (limit,),
        ).fetchall()
        return [_serialize_user(row) for row in rows]
    finally:
        conn.close()


def deletar_usuario(usuario_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM usuarios WHERE id = %s",
            (usuario_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def atualizar_role_usuario(usuario_id: int, role: str):
    role = normalize_role(role)
    if role not in MANAGED_ROLES:
        raise ValueError('Perfil de usuario invalido.')

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE usuarios SET role = %s WHERE id = %s",
            (role, usuario_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def autenticar_usuario(email: str, senha: str):
    usuario = buscar_usuario_por_email(email)
    if not usuario:
        return None, 'invalid_credentials'

    bloqueado_ate = usuario.get('bloqueado_ate')
    agora = datetime.utcnow()
    if bloqueado_ate and hasattr(bloqueado_ate, 'replace') and bloqueado_ate > agora:
        return None, 'temporarily_locked'

    if not check_password_hash(usuario['senha_hash'], senha):
        bloqueio_ate = registrar_falha_login(usuario['id'])
        if bloqueio_ate:
            return None, 'temporarily_locked'
        return None, 'invalid_credentials'

    if not usuario.get('email_verificado'):
        return usuario, 'email_not_verified'

    limpar_estado_login(usuario['id'])
    usuario = buscar_usuario_por_id(usuario['id'])
    return usuario, None


def registrar_falha_login(usuario_id: int):
    conn = get_connection()
    try:
        usuario = conn.execute(
            """SELECT tentativas_login_falhas, bloqueado_ate
               FROM usuarios
               WHERE id = %s""",
            (usuario_id,),
        ).fetchone()
        if not usuario:
            return None

        agora = datetime.utcnow()
        tentativas = int(usuario.get('tentativas_login_falhas') or 0) + 1
        bloqueado_ate = None
        if tentativas >= MAX_LOGIN_ATTEMPTS:
            bloqueado_ate = agora + timedelta(minutes=LOCK_MINUTES)
            tentativas = 0

        conn.execute(
            """UPDATE usuarios
               SET tentativas_login_falhas = %s,
                   bloqueado_ate = %s
               WHERE id = %s""",
            (tentativas, bloqueado_ate, usuario_id),
        )
        conn.commit()
        return bloqueado_ate
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def limpar_estado_login(usuario_id: int):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE usuarios
               SET tentativas_login_falhas = 0,
                   bloqueado_ate = NULL,
                   ultimo_login_em = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (usuario_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def marcar_email_como_verificado(usuario_id: int):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE usuarios
               SET email_verificado = 1,
                   email_verificado_em = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (usuario_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def atualizar_senha(usuario_id: int, nova_senha: str, validar_email: bool = True):
    conn = get_connection()
    try:
        senha_hash = generate_password_hash(nova_senha)
        if validar_email:
            conn.execute(
                """UPDATE usuarios
                   SET senha_hash = %s,
                       token_version = token_version + 1,
                       tentativas_login_falhas = 0,
                       bloqueado_ate = NULL,
                       email_verificado = 1,
                       email_verificado_em = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (senha_hash, usuario_id),
            )
        else:
            conn.execute(
                """UPDATE usuarios
                   SET senha_hash = %s,
                       token_version = token_version + 1,
                       tentativas_login_falhas = 0,
                       bloqueado_ate = NULL
                   WHERE id = %s""",
                (senha_hash, usuario_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _serialize_user(row):
    if not row:
        return None

    user = dict(row)
    user['role'] = normalize_role(user.get('role'))
    user['dias_desde_ultimo_login'] = _calculate_days_since_last_login(user.get('ultimo_login_em'))
    user['ultimo_login_label'] = _format_last_login_label(user['dias_desde_ultimo_login'])
    return user


def _calculate_days_since_last_login(last_login):
    if not last_login:
        return None

    now = datetime.utcnow()
    if hasattr(last_login, 'tzinfo') and last_login.tzinfo is not None:
        last_login = last_login.replace(tzinfo=None)

    delta = now - last_login
    return max(delta.days, 0)


def _format_last_login_label(days_since_last_login):
    if days_since_last_login is None:
        return 'Nunca'
    if days_since_last_login == 0:
        return 'Hoje'
    if days_since_last_login == 1:
        return '1 dia'
    return f'{days_since_last_login} dias'
