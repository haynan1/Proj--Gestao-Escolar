import logging
import os

from werkzeug.security import generate_password_hash

from access_control import ROLE_ADMIN
from database.connection import get_connection


LOGGER = logging.getLogger(__name__)

TABLE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        senha_hash VARCHAR(255) NOT NULL,
        role VARCHAR(30) NOT NULL DEFAULT 'funcionario',
        email_verificado TINYINT(1) NOT NULL DEFAULT 0,
        email_verificado_em TIMESTAMP NULL DEFAULT NULL,
        token_version INT NOT NULL DEFAULT 0,
        tentativas_login_falhas INT NOT NULL DEFAULT 0,
        bloqueado_ate TIMESTAMP NULL DEFAULT NULL,
        ultimo_login_em TIMESTAMP NULL DEFAULT NULL,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS escolas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NULL,
        nome VARCHAR(255) NOT NULL,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_escolas_usuario_nome (user_id, nome),
        CONSTRAINT fk_escolas_usuario
            FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS usuarios_escolas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NOT NULL,
        escola_id INT NOT NULL,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_usuarios_escolas (usuario_id, escola_id),
        CONSTRAINT fk_usuarios_escolas_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        CONSTRAINT fk_usuarios_escolas_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS disciplinas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        nome VARCHAR(255) NOT NULL,
        cor VARCHAR(20) NOT NULL DEFAULT '#22c55e',
        CONSTRAINT fk_disciplinas_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS professores (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        nome VARCHAR(255) NOT NULL,
        disciplina_id INT NOT NULL,
        max_aulas_semana INT NOT NULL DEFAULT 10,
        dias_disponiveis TEXT NOT NULL,
        CONSTRAINT fk_professores_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
        CONSTRAINT fk_professores_disciplina
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS turmas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        nome VARCHAR(255) NOT NULL,
        CONSTRAINT fk_turmas_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS aulas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        turma_id INT NOT NULL,
        professor_id INT NOT NULL,
        disciplina_id INT NOT NULL,
        dia VARCHAR(20) NOT NULL,
        periodo INT NOT NULL,
        UNIQUE KEY uq_aulas_turma_slot (turma_id, dia, periodo),
        UNIQUE KEY uq_aulas_professor_slot (professor_id, dia, periodo),
        CONSTRAINT fk_aulas_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
        CONSTRAINT fk_aulas_turma
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
        CONSTRAINT fk_aulas_professor
            FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
        CONSTRAINT fk_aulas_disciplina
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def _column_exists(cursor, table_name, column_name):
    row = cursor.execute(
        """SELECT COUNT(*) AS total
           FROM information_schema.columns
           WHERE table_schema = DATABASE()
             AND table_name = %s
             AND column_name = %s""",
        (table_name, column_name),
    ).fetchone()
    return bool(row and row['total'])


def _constraint_exists(cursor, table_name, constraint_name):
    row = cursor.execute(
        """SELECT COUNT(*) AS total
           FROM information_schema.table_constraints
           WHERE table_schema = DATABASE()
             AND table_name = %s
             AND constraint_name = %s""",
        (table_name, constraint_name),
    ).fetchone()
    return bool(row and row['total'])


def _index_exists(cursor, table_name, index_name):
    row = cursor.execute(
        """SELECT COUNT(*) AS total
           FROM information_schema.statistics
           WHERE table_schema = DATABASE()
             AND table_name = %s
             AND index_name = %s""",
        (table_name, index_name),
    ).fetchone()
    return bool(row and row['total'])


def _ensure_user_security_columns(cursor):
    if not _column_exists(cursor, 'usuarios', 'role'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'funcionario' AFTER senha_hash"
        )

    if not _column_exists(cursor, 'usuarios', 'email_verificado'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN email_verificado TINYINT(1) NOT NULL DEFAULT 1 AFTER role"
        )

    if not _column_exists(cursor, 'usuarios', 'email_verificado_em'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN email_verificado_em TIMESTAMP NULL DEFAULT NULL AFTER email_verificado"
        )
        cursor.execute(
            """UPDATE usuarios
               SET email_verificado_em = criado_em
               WHERE email_verificado = 1 AND email_verificado_em IS NULL"""
        )

    if not _column_exists(cursor, 'usuarios', 'token_version'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN token_version INT NOT NULL DEFAULT 0 AFTER email_verificado_em"
        )

    if not _column_exists(cursor, 'usuarios', 'tentativas_login_falhas'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN tentativas_login_falhas INT NOT NULL DEFAULT 0 AFTER token_version"
        )

    if not _column_exists(cursor, 'usuarios', 'bloqueado_ate'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN bloqueado_ate TIMESTAMP NULL DEFAULT NULL AFTER tentativas_login_falhas"
        )

    if not _column_exists(cursor, 'usuarios', 'ultimo_login_em'):
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN ultimo_login_em TIMESTAMP NULL DEFAULT NULL AFTER bloqueado_ate"
        )


def _ensure_school_owner_column(cursor):
    if not _column_exists(cursor, 'escolas', 'user_id'):
        cursor.execute("ALTER TABLE escolas ADD COLUMN user_id INT NULL AFTER id")

    if not _index_exists(cursor, 'escolas', 'idx_escolas_user_id'):
        cursor.execute("CREATE INDEX idx_escolas_user_id ON escolas (user_id)")

    if not _constraint_exists(cursor, 'escolas', 'fk_escolas_usuario'):
        cursor.execute(
            """ALTER TABLE escolas
               ADD CONSTRAINT fk_escolas_usuario
               FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE"""
        )

    if not _constraint_exists(cursor, 'escolas', 'uq_escolas_usuario_nome'):
        row = cursor.execute(
            """SELECT index_name
               FROM information_schema.statistics
               WHERE table_schema = DATABASE()
                 AND table_name = 'escolas'
                 AND column_name = 'nome'
                 AND non_unique = 0
                 AND index_name <> 'PRIMARY'
               ORDER BY seq_in_index ASC
               LIMIT 1"""
        ).fetchone()
        if row and row['index_name'] != 'uq_escolas_usuario_nome':
            cursor.execute(f"ALTER TABLE escolas DROP INDEX {row['index_name']}")
        cursor.execute(
            "ALTER TABLE escolas ADD CONSTRAINT uq_escolas_usuario_nome UNIQUE (user_id, nome)"
        )


def _ensure_user_school_links(cursor):
    if _constraint_exists(cursor, 'usuarios_escolas', 'fk_usuarios_escolas_usuario'):
        return

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios_escolas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            escola_id INT NOT NULL,
            criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_usuarios_escolas (usuario_id, escola_id),
            CONSTRAINT fk_usuarios_escolas_usuario
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            CONSTRAINT fk_usuarios_escolas_escola
                FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _ensure_bootstrap_admin(cursor):
    email = os.getenv('AUTH_BOOTSTRAP_ADMIN_EMAIL', '').strip().lower()
    password = os.getenv('AUTH_BOOTSTRAP_ADMIN_PASSWORD', '').strip()
    name = os.getenv('AUTH_BOOTSTRAP_ADMIN_NAME', 'Administrador').strip() or 'Administrador'

    if not email or not password:
        return

    existing = cursor.execute(
        "SELECT id FROM usuarios WHERE email = %s",
        (email,),
    ).fetchone()
    if existing:
        cursor.execute(
            """UPDATE usuarios
               SET role = %s,
                   email_verificado = 1,
                   email_verificado_em = COALESCE(email_verificado_em, CURRENT_TIMESTAMP),
                   tentativas_login_falhas = 0,
                   bloqueado_ate = NULL
               WHERE id = %s""",
            (ROLE_ADMIN, existing['id']),
        )
        return

    cursor.execute(
        """INSERT INTO usuarios (
               nome,
               email,
               senha_hash,
               role,
               email_verificado,
               email_verificado_em,
               token_version,
               tentativas_login_falhas
           ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)""",
        (name, email, generate_password_hash(password), ROLE_ADMIN, True, 0, 0),
    )


def _assign_legacy_schools(cursor):
    row = cursor.execute(
        "SELECT COUNT(*) AS total FROM escolas WHERE user_id IS NULL"
    ).fetchone()
    if not row or not row['total']:
        return

    owner_email = os.getenv('AUTH_ASSIGN_LEGACY_SCHOOLS_TO_EMAIL', '').strip().lower()
    if not owner_email:
        LOGGER.warning(
            'Existem escolas legadas sem owner definido. '
            'Configure AUTH_ASSIGN_LEGACY_SCHOOLS_TO_EMAIL para vincula-las com seguranca.'
        )
        return

    owner = cursor.execute(
        "SELECT id FROM usuarios WHERE email = %s",
        (owner_email,),
    ).fetchone()
    if not owner:
        LOGGER.warning(
            'AUTH_ASSIGN_LEGACY_SCHOOLS_TO_EMAIL=%s nao corresponde a nenhum usuario.',
            owner_email,
        )
        return

    cursor.execute(
        "UPDATE escolas SET user_id = %s WHERE user_id IS NULL",
        (owner['id'],),
    )


def _backfill_school_links(cursor):
    cursor.execute(
        """INSERT IGNORE INTO usuarios_escolas (usuario_id, escola_id)
           SELECT user_id, id
           FROM escolas
           WHERE user_id IS NOT NULL"""
    )


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for statement in TABLE_STATEMENTS:
            cursor.execute(statement)
        _ensure_user_security_columns(conn)
        _ensure_school_owner_column(conn)
        _ensure_user_school_links(conn)
        _ensure_bootstrap_admin(conn)
        _assign_legacy_schools(conn)
        _backfill_school_links(conn)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
