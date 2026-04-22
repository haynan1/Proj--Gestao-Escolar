from database.connection import get_connection


def criar_turma(escola_id, nome):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO turmas (escola_id, nome) VALUES (%s, %s)",
            (escola_id, nome)
        )
        conn.commit()
        return True, "Turma criada com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def listar_turmas(escola_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM turmas WHERE escola_id = %s ORDER BY nome", (escola_id,)
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


def atualizar_turma(turma_id, escola_id, nome):
    conn = get_connection()
    conn.execute(
        "UPDATE turmas SET nome = %s WHERE id = %s AND escola_id = %s",
        (nome, turma_id, escola_id),
    )
    conn.commit()
    conn.close()


def deletar_turma(turma_id, escola_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM turmas WHERE id = %s AND escola_id = %s",
        (turma_id, escola_id),
    )
    conn.commit()
    conn.close()
