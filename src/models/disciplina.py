from database.connection import get_connection


def criar_disciplina(escola_id, nome, cor):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO disciplinas (escola_id, nome, cor) VALUES (?, ?, ?)",
            (escola_id, nome, cor)
        )
        conn.commit()
        return True, "Disciplina criada com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def listar_disciplinas(escola_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM disciplinas WHERE escola_id = ? ORDER BY nome", (escola_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_disciplina(disciplina_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM disciplinas WHERE id = ?", (disciplina_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def atualizar_disciplina(disciplina_id, nome, cor):
    conn = get_connection()
    conn.execute(
        "UPDATE disciplinas SET nome = ?, cor = ? WHERE id = ?",
        (nome, cor, disciplina_id)
    )
    conn.commit()
    conn.close()


def deletar_disciplina(disciplina_id):
    conn = get_connection()
    conn.execute("DELETE FROM disciplinas WHERE id = ?", (disciplina_id,))
    conn.commit()
    conn.close()
