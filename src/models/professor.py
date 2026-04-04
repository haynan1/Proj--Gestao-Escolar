from database.connection import get_connection


def criar_professor(escola_id, nome, disciplina_id, max_aulas_semana, dias_disponiveis):
    conn = get_connection()
    try:
        dias_str = ','.join(dias_disponiveis) if isinstance(dias_disponiveis, list) else dias_disponiveis
        conn.execute(
            """INSERT INTO professores (escola_id, nome, disciplina_id, max_aulas_semana, dias_disponiveis)
               VALUES (?, ?, ?, ?, ?)""",
            (escola_id, nome, disciplina_id, max_aulas_semana, dias_str)
        )
        conn.commit()
        return True, "Professor criado com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def listar_professores(escola_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.*, d.nome AS disciplina_nome, d.cor AS disciplina_cor
           FROM professores p
           JOIN disciplinas d ON p.disciplina_id = d.id
           WHERE p.escola_id = ?
           ORDER BY p.nome""",
        (escola_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        item['dias_lista'] = item['dias_disponiveis'].split(',')
        result.append(item)
    return result


def buscar_professor(professor_id):
    conn = get_connection()
    row = conn.execute(
        """SELECT p.*, d.nome AS disciplina_nome
           FROM professores p
           JOIN disciplinas d ON p.disciplina_id = d.id
           WHERE p.id = ?""",
        (professor_id,)
    ).fetchone()
    conn.close()
    if row:
        item = dict(row)
        item['dias_lista'] = item['dias_disponiveis'].split(',')
        return item
    return None


def atualizar_professor(professor_id, nome, disciplina_id, max_aulas_semana, dias_disponiveis):
    conn = get_connection()
    dias_str = ','.join(dias_disponiveis) if isinstance(dias_disponiveis, list) else dias_disponiveis
    conn.execute(
        """UPDATE professores SET nome = ?, disciplina_id = ?, max_aulas_semana = ?, dias_disponiveis = ?
           WHERE id = ?""",
        (nome, disciplina_id, max_aulas_semana, dias_str, professor_id)
    )
    conn.commit()
    conn.close()


def deletar_professor(professor_id):
    conn = get_connection()
    conn.execute("DELETE FROM professores WHERE id = ?", (professor_id,))
    conn.commit()
    conn.close()
