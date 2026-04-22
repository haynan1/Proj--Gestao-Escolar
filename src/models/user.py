from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from database.connection import get_connection


MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15


def criar_usuario(nome: str, email: str, senha: str):
    conn = get_connection()
    try:
        senha_hash = generate_password_hash(senha)
        conn.execute(
            """INSERT INTO usuarios (
                   nome,
                   email,
                   senha_hash,
                   email_verificado,
                   tentativas_login_falhas,
                   token_version
               ) VALUES (%s, %s, %s, %s, %s, %s)""",
            (nome, email.lower(), senha_hash, False, 0, 0),
        )
        conn.commit()
        return True, 'Usuário criado com sucesso.'
    except Exception as exc:
        conn.rollback()
        mensagem = str(exc)
        if 'Duplicate entry' in mensagem and 'usuarios.email' in mensagem:
            return False, 'Já existe um usuário cadastrado com este e-mail.'
        return False, mensagem
    finally:
        conn.close()


def buscar_usuario_por_email(email: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE email = %s",
            (email.lower(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def buscar_usuario_por_id(usuario_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id = %s",
            (usuario_id,),
        ).fetchone()
        return dict(row) if row else None
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
    finally:
        conn.close()
