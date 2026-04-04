from database.connection import get_connection


def criar_turma(escola_id, nome):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO turmas (escola_id, nome) VALUES (?, ?)",
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
        "SELECT * FROM turmas WHERE escola_id = ? ORDER BY nome", (escola_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_turma(turma_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM turmas WHERE id = ?", (turma_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def atualizar_turma(turma_id, nome):
    conn = get_connection()
    conn.execute("UPDATE turmas SET nome = ? WHERE id = ?", (nome, turma_id))
    conn.commit()
    conn.close()


def deletar_turma(turma_id):
    conn = get_connection()
    conn.execute("DELETE FROM turmas WHERE id = ?", (turma_id,))
    conn.commit()
    conn.close()
