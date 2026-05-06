import re

from database.connection import get_connection
from models.turno import normalizar_turno


COR_DISCIPLINA_PADRAO = '#22c55e'
HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _normalizar_cor(cor):
    cor = (cor or '').strip()
    if HEX_COLOR_PATTERN.fullmatch(cor):
        return cor
    return None


class DisciplineInUseError(ValueError):
    """Raised when trying to delete a discipline linked to teachers."""


def _disciplina_nome_existe(conn, escola_id, turno, nome, ignorar_id=None):
    params = [escola_id, turno, nome.strip()]
    filtro_ignorar = ''
    if ignorar_id is not None:
        filtro_ignorar = ' AND id <> %s'
        params.append(ignorar_id)

    row = conn.execute(
        f"""SELECT id
            FROM disciplinas
            WHERE escola_id = %s
              AND turno = %s
              AND LOWER(TRIM(nome)) = LOWER(TRIM(%s))
              {filtro_ignorar}
            LIMIT 1""",
        tuple(params),
    ).fetchone()
    return bool(row)


def criar_disciplina(escola_id, nome, cor, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        if _disciplina_nome_existe(conn, escola_id, turno, nome):
            return False, "Ja existe uma disciplina com esse nome neste turno."
        conn.execute(
            "INSERT INTO disciplinas (escola_id, turno, nome, cor) VALUES (%s, %s, %s, %s)",
            (escola_id, turno, nome, _normalizar_cor(cor))
        )
        conn.commit()
        return True, "Disciplina criada com sucesso."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def listar_disciplinas(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM disciplinas WHERE escola_id = %s AND turno = %s ORDER BY nome",
        (escola_id, turno),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_disciplina(disciplina_id, escola_id=None):
    conn = get_connection()
    if escola_id is None:
        row = conn.execute("SELECT * FROM disciplinas WHERE id = %s", (disciplina_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM disciplinas WHERE id = %s AND escola_id = %s",
            (disciplina_id, escola_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def atualizar_disciplina(disciplina_id, escola_id, nome, cor, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        if _disciplina_nome_existe(conn, escola_id, turno, nome, disciplina_id):
            raise ValueError("Ja existe uma disciplina com esse nome neste turno.")
        conn.execute(
            "UPDATE disciplinas SET nome = %s, cor = %s WHERE id = %s AND escola_id = %s AND turno = %s",
            (nome, _normalizar_cor(cor), disciplina_id, escola_id, turno)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_disciplina(disciplina_id, escola_id):
    conn = get_connection()
    try:
        professores_vinculados = conn.execute(
            """SELECT COUNT(*) AS total
               FROM professores_disciplinas pd
               JOIN professores p ON p.id = pd.professor_id
               WHERE pd.disciplina_id = %s AND p.escola_id = %s""",
            (disciplina_id, escola_id),
        ).fetchone()
        if professores_vinculados and professores_vinculados['total'] > 0:
            raise DisciplineInUseError(
                "Não é possível remover a disciplina porque existem professores vinculados a ela."
            )

        conn.execute(
            "DELETE FROM disciplinas WHERE id = %s AND escola_id = %s",
            (disciplina_id, escola_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
