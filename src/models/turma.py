from database.connection import get_connection
from models.turno import normalizar_turno


def _normalizar_aulas_por_dia(aulas_por_dia):
    try:
        valor = int(aulas_por_dia)
    except (TypeError, ValueError):
        valor = 5
    return valor if valor in (5, 6) else 5


def criar_turma(escola_id, nome, aulas_por_dia=5, turno=None):
    turno = normalizar_turno(turno)
    aulas_por_dia = _normalizar_aulas_por_dia(aulas_por_dia)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO turmas (escola_id, turno, nome, aulas_por_dia) VALUES (%s, %s, %s, %s)",
            (escola_id, turno, nome, aulas_por_dia)
        )
        conn.commit()
        return True, "Turma criada com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def listar_turmas(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM turmas WHERE escola_id = %s AND turno = %s ORDER BY nome",
        (escola_id, turno),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_turma(turma_id, escola_id=None):
    conn = get_connection()
    if escola_id is None:
        row = conn.execute("SELECT * FROM turmas WHERE id = %s", (turma_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM turmas WHERE id = %s AND escola_id = %s",
            (turma_id, escola_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def atualizar_turma(turma_id, escola_id, nome, aulas_por_dia=5):
    aulas_por_dia = _normalizar_aulas_por_dia(aulas_por_dia)
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE turmas
               SET nome = %s,
                   aulas_por_dia = %s
               WHERE id = %s AND escola_id = %s""",
            (nome, aulas_por_dia, turma_id, escola_id),
        )
        conn.execute(
            """DELETE FROM aulas
               WHERE escola_id = %s
                 AND turma_id = %s
                 AND periodo > %s""",
            (escola_id, turma_id, aulas_por_dia),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_turma(turma_id, escola_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM turmas WHERE id = %s AND escola_id = %s",
        (turma_id, escola_id),
    )
    conn.commit()
    conn.close()
