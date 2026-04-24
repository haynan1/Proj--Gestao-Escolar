from database.connection import get_connection


def _normalizar_turma_ids(turma_ids):
    if not turma_ids:
        return []
    ids = []
    for turma_id in turma_ids:
        try:
            ids.append(int(turma_id))
        except (TypeError, ValueError):
            continue
    return sorted(set(ids))


def _sincronizar_turmas_professor(conn, professor_id, escola_id, turma_ids):
    conn.execute(
        "DELETE FROM professores_turmas WHERE professor_id = %s",
        (professor_id,),
    )

    turma_ids = _normalizar_turma_ids(turma_ids)
    for turma_id in turma_ids:
        conn.execute(
            """INSERT INTO professores_turmas (professor_id, turma_id)
               SELECT %s, id
               FROM turmas
               WHERE id = %s AND escola_id = %s""",
            (professor_id, turma_id, escola_id),
        )


def _anexar_turmas(professores):
    if not professores:
        return professores

    professor_ids = [p['id'] for p in professores]
    placeholders = ', '.join(['%s'] * len(professor_ids))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""SELECT pt.professor_id, t.id AS turma_id, t.nome AS turma_nome
                FROM professores_turmas pt
                JOIN turmas t ON t.id = pt.turma_id
                WHERE pt.professor_id IN ({placeholders})
                ORDER BY t.nome""",
            tuple(professor_ids),
        ).fetchall()
    finally:
        conn.close()

    turmas_por_professor = {prof_id: [] for prof_id in professor_ids}
    for row in rows:
        turmas_por_professor[row['professor_id']].append({
            'id': row['turma_id'],
            'nome': row['turma_nome'],
        })

    for professor in professores:
        turmas = turmas_por_professor.get(professor['id'], [])
        professor['turmas_lista'] = turmas
        professor['turma_ids'] = [turma['id'] for turma in turmas]
        professor['turmas_nomes'] = ', '.join(turma['nome'] for turma in turmas)

    return professores


def criar_professor(escola_id, nome, disciplina_id, max_aulas_semana, dias_disponiveis, turma_ids=None):
    conn = get_connection()
    try:
        dias_str = ','.join(dias_disponiveis) if isinstance(dias_disponiveis, list) else dias_disponiveis
        cursor = conn.execute(
            """INSERT INTO professores (escola_id, nome, disciplina_id, max_aulas_semana, dias_disponiveis)
               VALUES (%s, %s, %s, %s, %s)""",
            (escola_id, nome, disciplina_id, max_aulas_semana, dias_str)
        )
        _sincronizar_turmas_professor(conn, cursor.lastrowid, escola_id, turma_ids)
        conn.commit()
        return True, "Professor criado com sucesso."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def listar_professores(escola_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.*, d.nome AS disciplina_nome, d.cor AS disciplina_cor
           FROM professores p
           JOIN disciplinas d ON p.disciplina_id = d.id
           WHERE p.escola_id = %s
           ORDER BY p.nome""",
        (escola_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        item['dias_lista'] = item['dias_disponiveis'].split(',')
        result.append(item)
    return _anexar_turmas(result)


def buscar_professor(professor_id, escola_id=None):
    conn = get_connection()
    if escola_id is None:
        row = conn.execute(
            """SELECT p.*, d.nome AS disciplina_nome
               FROM professores p
               JOIN disciplinas d ON p.disciplina_id = d.id
               WHERE p.id = %s""",
            (professor_id,)
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT p.*, d.nome AS disciplina_nome
               FROM professores p
               JOIN disciplinas d ON p.disciplina_id = d.id
               WHERE p.id = %s AND p.escola_id = %s""",
            (professor_id, escola_id)
        ).fetchone()
    conn.close()
    if row:
        item = dict(row)
        item['dias_lista'] = item['dias_disponiveis'].split(',')
        return _anexar_turmas([item])[0]
    return None


def atualizar_professor(professor_id, escola_id, nome, disciplina_id, max_aulas_semana, dias_disponiveis, turma_ids=None):
    conn = get_connection()
    try:
        dias_str = ','.join(dias_disponiveis) if isinstance(dias_disponiveis, list) else dias_disponiveis
        conn.execute(
            """UPDATE professores SET nome = %s, disciplina_id = %s, max_aulas_semana = %s, dias_disponiveis = %s
               WHERE id = %s AND escola_id = %s""",
            (nome, disciplina_id, max_aulas_semana, dias_str, professor_id, escola_id)
        )
        _sincronizar_turmas_professor(conn, professor_id, escola_id, turma_ids)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_professor(professor_id, escola_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM professores WHERE id = %s AND escola_id = %s",
        (professor_id, escola_id),
    )
    conn.commit()
    conn.close()
