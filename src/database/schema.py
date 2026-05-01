import logging
import os

from werkzeug.security import generate_password_hash

from access_control import ROLE_ADMIN, ROLE_STAFF
from database.connection import get_connection


LOGGER = logging.getLogger(__name__)
DEFAULT_TEST_USER_NAME = 'Teste'
DEFAULT_TEST_USER_EMAIL = 'teste@escola.com'
DEFAULT_TEST_USER_PASSWORD = 'Teste12345'
LEGACY_TEST_USER_EMAILS = ('teste_review3@example.com',)
DEFAULT_SCHOOL_DAYS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']

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
        oculta TINYINT(1) NOT NULL DEFAULT 0,
        backup_de_escola_id INT NULL,
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
        turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
        nome VARCHAR(255) NOT NULL,
        cor VARCHAR(20) NULL DEFAULT NULL,
        CONSTRAINT fk_disciplinas_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS professores (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
        nome VARCHAR(255) NOT NULL,
        cor VARCHAR(20) NULL DEFAULT NULL,
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
    CREATE TABLE IF NOT EXISTS professores_disciplinas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        professor_id INT NOT NULL,
        disciplina_id INT NOT NULL,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_professores_disciplinas (professor_id, disciplina_id),
        CONSTRAINT fk_professores_disciplinas_professor
            FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
        CONSTRAINT fk_professores_disciplinas_disciplina
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS turmas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
        nome VARCHAR(255) NOT NULL,
        aulas_por_dia INT NOT NULL DEFAULT 5,
        CONSTRAINT fk_turmas_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS professores_turmas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        professor_id INT NOT NULL,
        turma_id INT NOT NULL,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_professores_turmas (professor_id, turma_id),
        CONSTRAINT fk_professores_turmas_professor
            FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
        CONSTRAINT fk_professores_turmas_turma
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS professores_cargas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        professor_id INT NOT NULL,
        turma_id INT NOT NULL,
        disciplina_id INT NOT NULL,
        aulas_semana INT NOT NULL DEFAULT 1,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_professores_cargas (professor_id, turma_id, disciplina_id),
        CONSTRAINT fk_professores_cargas_professor
            FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
        CONSTRAINT fk_professores_cargas_turma
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
        CONSTRAINT fk_professores_cargas_disciplina
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS aulas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
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
    """
    CREATE TABLE IF NOT EXISTS horarios_temporarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        escola_id INT NOT NULL,
        turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
        turma_id INT NOT NULL,
        data_inicio DATE NOT NULL,
        data_fim DATE NOT NULL,
        dia VARCHAR(20) NOT NULL,
        periodo INT NOT NULL,
        titulo VARCHAR(255) NOT NULL,
        professor_id INT NULL,
        disciplina_id INT NULL,
        observacao TEXT NULL,
        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY idx_horarios_temp_escola_turno (escola_id, turno),
        KEY idx_horarios_temp_turma_datas (turma_id, data_inicio, data_fim),
        CONSTRAINT fk_horarios_temp_escola
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
        CONSTRAINT fk_horarios_temp_turma
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
        CONSTRAINT fk_horarios_temp_professor
            FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE SET NULL,
        CONSTRAINT fk_horarios_temp_disciplina
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE SET NULL
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


def _ensure_school_backup_columns(cursor):
    if not _column_exists(cursor, 'escolas', 'oculta'):
        cursor.execute(
            "ALTER TABLE escolas ADD COLUMN oculta TINYINT(1) NOT NULL DEFAULT 0 AFTER nome"
        )

    if not _column_exists(cursor, 'escolas', 'backup_de_escola_id'):
        cursor.execute(
            "ALTER TABLE escolas ADD COLUMN backup_de_escola_id INT NULL AFTER oculta"
        )

    if not _index_exists(cursor, 'escolas', 'idx_escolas_oculta'):
        cursor.execute("CREATE INDEX idx_escolas_oculta ON escolas (oculta)")

    if not _index_exists(cursor, 'escolas', 'idx_escolas_backup_de'):
        cursor.execute("CREATE INDEX idx_escolas_backup_de ON escolas (backup_de_escola_id)")


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


def _ensure_turma_period_columns(cursor):
    if not _column_exists(cursor, 'turmas', 'aulas_por_dia'):
        cursor.execute(
            "ALTER TABLE turmas ADD COLUMN aulas_por_dia INT NOT NULL DEFAULT 5 AFTER nome"
        )


def _ensure_turno_columns(cursor):
    turno_columns = (
        ('disciplinas', 'escola_id'),
        ('turmas', 'escola_id'),
        ('professores', 'escola_id'),
        ('aulas', 'escola_id'),
    )
    for table_name, after_column in turno_columns:
        if not _column_exists(cursor, table_name, 'turno'):
            cursor.execute(
                f"ALTER TABLE {table_name} "
                f"ADD COLUMN turno VARCHAR(20) NOT NULL DEFAULT 'matutino' AFTER {after_column}"
            )

        index_name = f"idx_{table_name}_escola_turno"
        if not _index_exists(cursor, table_name, index_name):
            cursor.execute(f"CREATE INDEX {index_name} ON {table_name} (escola_id, turno)")


def _ensure_disciplina_color_column(cursor):
    if not _column_exists(cursor, 'disciplinas', 'cor'):
        cursor.execute(
            "ALTER TABLE disciplinas ADD COLUMN cor VARCHAR(20) NULL DEFAULT NULL AFTER nome"
        )
    else:
        cursor.execute(
            "ALTER TABLE disciplinas MODIFY COLUMN cor VARCHAR(20) NULL DEFAULT NULL"
        )


def _ensure_professor_color_column(cursor):
    if not _column_exists(cursor, 'professores', 'cor'):
        cursor.execute(
            "ALTER TABLE professores ADD COLUMN cor VARCHAR(20) NULL DEFAULT NULL AFTER nome"
        )
    else:
        cursor.execute(
            "ALTER TABLE professores MODIFY COLUMN cor VARCHAR(20) NULL DEFAULT NULL"
        )


def _backfill_professor_turma_links(cursor):
    cursor.execute(
        """INSERT IGNORE INTO professores_turmas (professor_id, turma_id)
           SELECT p.id, t.id
           FROM professores p
           JOIN turmas t ON t.escola_id = p.escola_id
           WHERE NOT EXISTS (
               SELECT 1
               FROM professores_turmas pt
               WHERE pt.professor_id = p.id
           )"""
    )


def _backfill_professor_disciplina_links(cursor):
    cursor.execute(
        """INSERT IGNORE INTO professores_disciplinas (professor_id, disciplina_id)
           SELECT id, disciplina_id
           FROM professores"""
    )


def _merge_duplicate_professors(conn):
    duplicates = conn.execute(
        """SELECT escola_id, LOWER(TRIM(nome)) AS nome_normalizado
           FROM professores
           GROUP BY escola_id, LOWER(TRIM(nome))
           HAVING COUNT(*) > 1"""
    ).fetchall()

    for group in duplicates:
        professores = conn.execute(
            """SELECT *
               FROM professores
               WHERE escola_id = %s AND LOWER(TRIM(nome)) = %s
               ORDER BY id""",
            (group['escola_id'], group['nome_normalizado']),
        ).fetchall()
        if len(professores) < 2:
            continue

        principal = professores[0]
        principal_id = principal['id']
        dias = set(filter(None, (principal.get('dias_disponiveis') or '').split(',')))
        max_aulas = int(principal.get('max_aulas_semana') or 0)

        for duplicado in professores[1:]:
            duplicado_id = duplicado['id']
            conflito = conn.execute(
                """SELECT COUNT(*) AS total
                   FROM aulas a_dup
                   JOIN aulas a_main
                     ON a_main.professor_id = %s
                    AND a_main.dia = a_dup.dia
                    AND a_main.periodo = a_dup.periodo
                   WHERE a_dup.professor_id = %s""",
                (principal_id, duplicado_id),
            ).fetchone()
            if conflito and conflito['total'] > 0:
                LOGGER.warning(
                    'Professor duplicado %s nao foi mesclado por conflito de horarios.',
                    duplicado.get('nome'),
                )
                continue

            conn.execute(
                """INSERT IGNORE INTO professores_disciplinas (professor_id, disciplina_id)
                   SELECT %s, disciplina_id
                   FROM professores_disciplinas
                   WHERE professor_id = %s""",
                (principal_id, duplicado_id),
            )
            conn.execute(
                """INSERT IGNORE INTO professores_turmas (professor_id, turma_id)
                   SELECT %s, turma_id
                   FROM professores_turmas
                   WHERE professor_id = %s""",
                (principal_id, duplicado_id),
            )
            conn.execute(
                "UPDATE aulas SET professor_id = %s WHERE professor_id = %s",
                (principal_id, duplicado_id),
            )
            conn.execute(
                "DELETE FROM professores WHERE id = %s",
                (duplicado_id,),
            )

            dias.update(filter(None, (duplicado.get('dias_disponiveis') or '').split(',')))
            max_aulas = max(max_aulas, int(duplicado.get('max_aulas_semana') or 0))

        conn.execute(
            """UPDATE professores
               SET max_aulas_semana = %s,
                   dias_disponiveis = %s
               WHERE id = %s""",
            (
                max_aulas or principal.get('max_aulas_semana'),
                ','.join(_sort_school_days(dias)),
                principal_id,
            ),
        )


def _sort_school_days(days):
    order = {day: index for index, day in enumerate(DEFAULT_SCHOOL_DAYS)}
    return sorted(days, key=lambda day: order.get(day, len(order)))


def _normalize_professor_days(conn):
    professores = conn.execute(
        "SELECT id, dias_disponiveis FROM professores"
    ).fetchall()
    for professor in professores:
        days = set(filter(None, (professor.get('dias_disponiveis') or '').split(',')))
        conn.execute(
            "UPDATE professores SET dias_disponiveis = %s WHERE id = %s",
            (','.join(_sort_school_days(days)), professor['id']),
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


def _ensure_system_test_user(cursor):
    email = os.getenv('AUTH_TEST_USER_EMAIL', DEFAULT_TEST_USER_EMAIL).strip().lower()
    password = os.getenv('AUTH_TEST_USER_PASSWORD', DEFAULT_TEST_USER_PASSWORD).strip()
    name = os.getenv('AUTH_TEST_USER_NAME', DEFAULT_TEST_USER_NAME).strip() or DEFAULT_TEST_USER_NAME

    if not email or not password:
        return

    existing = cursor.execute(
        "SELECT id FROM usuarios WHERE email = %s",
        (email,),
    ).fetchone()
    if not existing:
        placeholders = ', '.join(['%s'] * len(LEGACY_TEST_USER_EMAILS))
        existing = cursor.execute(
            f"SELECT id FROM usuarios WHERE email IN ({placeholders}) ORDER BY id LIMIT 1",
            LEGACY_TEST_USER_EMAILS,
        ).fetchone()

    if existing:
        cursor.execute(
            """UPDATE usuarios
               SET nome = %s,
                   email = %s,
                   senha_hash = %s,
                   role = %s,
                   email_verificado = 1,
                   email_verificado_em = COALESCE(email_verificado_em, CURRENT_TIMESTAMP),
                   token_version = token_version + 1,
                   tentativas_login_falhas = 0,
                   bloqueado_ate = NULL
               WHERE id = %s""",
            (name, email, generate_password_hash(password), ROLE_STAFF, existing['id']),
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
        (name, email, generate_password_hash(password), ROLE_STAFF, True, 0, 0),
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
        _ensure_school_backup_columns(conn)
        _ensure_user_school_links(conn)
        _ensure_turno_columns(conn)
        _ensure_turma_period_columns(conn)
        _ensure_disciplina_color_column(conn)
        _ensure_professor_color_column(conn)
        _ensure_bootstrap_admin(conn)
        _ensure_system_test_user(conn)
        _backfill_professor_disciplina_links(conn)
        _backfill_professor_turma_links(conn)
        _merge_duplicate_professors(conn)
        _normalize_professor_days(conn)
        _assign_legacy_schools(conn)
        _backfill_school_links(conn)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
