import re

from database.connection import get_connection


CORES_PROFESSOR = [
    '#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c',
    '#0891b2', '#4f46e5', '#be123c', '#0d9488', '#a16207',
    '#7c3aed', '#0284c7', '#65a30d', '#c2410c', '#db2777',
    '#4338ca', '#047857', '#b91c1c', '#0369a1', '#92400e',
]
COR_PROFESSOR_PADRAO = CORES_PROFESSOR[0]
HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _normalizar_cor(cor):
    cor = (cor or '').strip()
    if HEX_COLOR_PATTERN.fullmatch(cor):
        return cor
    return None


def _normalizar_ids(ids):
    if not ids:
        return []

    normalizados = []
    for item_id in ids:
        try:
            normalizados.append(int(item_id))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalizados))


def _normalizar_cargas(cargas):
    normalizadas = []
    vistos = set()
    if not cargas:
        return normalizadas

    for carga in cargas:
        try:
            turma_id = int(carga.get('turma_id'))
            disciplina_id = int(carga.get('disciplina_id'))
            aulas_semana = int(carga.get('aulas_semana') or 0)
        except (TypeError, ValueError, AttributeError):
            continue

        chave = (turma_id, disciplina_id)
        if aulas_semana <= 0 or chave in vistos:
            continue

        vistos.add(chave)
        normalizadas.append({
            'turma_id': turma_id,
            'disciplina_id': disciplina_id,
            'aulas_semana': aulas_semana,
        })

    return normalizadas


def _sincronizar_turmas_professor(conn, professor_id, escola_id, turma_ids):
    conn.execute(
        "DELETE FROM professores_turmas WHERE professor_id = %s",
        (professor_id,),
    )

    for turma_id in _normalizar_ids(turma_ids):
        conn.execute(
            """INSERT INTO professores_turmas (professor_id, turma_id)
               SELECT %s, id
               FROM turmas
               WHERE id = %s AND escola_id = %s""",
            (professor_id, turma_id, escola_id),
        )


def _sincronizar_disciplinas_professor(conn, professor_id, escola_id, disciplina_ids):
    conn.execute(
        "DELETE FROM professores_disciplinas WHERE professor_id = %s",
        (professor_id,),
    )

    for disciplina_id in _normalizar_ids(disciplina_ids):
        conn.execute(
            """INSERT INTO professores_disciplinas (professor_id, disciplina_id)
               SELECT %s, id
               FROM disciplinas
               WHERE id = %s AND escola_id = %s""",
            (professor_id, disciplina_id, escola_id),
        )


def _sincronizar_cargas_professor(conn, professor_id, escola_id, cargas):
    conn.execute(
        "DELETE FROM professores_cargas WHERE professor_id = %s",
        (professor_id,),
    )

    for carga in _normalizar_cargas(cargas):
        conn.execute(
            """INSERT INTO professores_cargas (
                   professor_id,
                   turma_id,
                   disciplina_id,
                   aulas_semana
               )
               SELECT %s, t.id, d.id, %s
               FROM turmas t
               JOIN disciplinas d ON d.id = %s AND d.escola_id = t.escola_id
               WHERE t.id = %s AND t.escola_id = %s""",
            (
                professor_id,
                carga['aulas_semana'],
                carga['disciplina_id'],
                carga['turma_id'],
                escola_id,
            ),
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


def _anexar_cargas(professores):
    if not professores:
        return professores

    professor_ids = [p['id'] for p in professores]
    placeholders = ', '.join(['%s'] * len(professor_ids))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""SELECT pc.professor_id,
                       pc.turma_id,
                       t.nome AS turma_nome,
                       pc.disciplina_id,
                       d.nome AS disciplina_nome,
                       d.cor AS disciplina_cor,
                       pc.aulas_semana
                FROM professores_cargas pc
                JOIN turmas t ON t.id = pc.turma_id
                JOIN disciplinas d ON d.id = pc.disciplina_id
                WHERE pc.professor_id IN ({placeholders})
                ORDER BY t.nome, d.nome""",
            tuple(professor_ids),
        ).fetchall()
    finally:
        conn.close()

    cargas_por_professor = {prof_id: [] for prof_id in professor_ids}
    for row in rows:
        carga = {
            'turma_id': row['turma_id'],
            'turma_nome': row['turma_nome'],
            'disciplina_id': row['disciplina_id'],
            'disciplina_nome': row['disciplina_nome'],
            'disciplina_cor': row['disciplina_cor'],
            'aulas_semana': row['aulas_semana'],
        }
        cargas_por_professor[row['professor_id']].append(carga)

    for professor in professores:
        cargas = cargas_por_professor.get(professor['id'], [])
        professor['cargas_lista'] = cargas
        professor['cargas_mapa'] = {
            f"{carga['turma_id']}:{carga['disciplina_id']}": carga['aulas_semana']
            for carga in cargas
        }

    return professores


def _anexar_disciplinas(professores):
    if not professores:
        return professores

    professor_ids = [p['id'] for p in professores]
    placeholders = ', '.join(['%s'] * len(professor_ids))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""SELECT pd.professor_id,
                       d.id AS disciplina_id,
                       d.nome AS disciplina_nome,
                       d.cor AS disciplina_cor
                FROM professores_disciplinas pd
                JOIN disciplinas d ON d.id = pd.disciplina_id
                WHERE pd.professor_id IN ({placeholders})
                ORDER BY d.nome""",
            tuple(professor_ids),
        ).fetchall()
    finally:
        conn.close()

    disciplinas_por_professor = {prof_id: [] for prof_id in professor_ids}
    for row in rows:
        disciplinas_por_professor[row['professor_id']].append({
            'id': row['disciplina_id'],
            'nome': row['disciplina_nome'],
            'cor': row['disciplina_cor'],
        })

    for professor in professores:
        disciplinas = disciplinas_por_professor.get(professor['id'], [])
        professor['disciplinas_lista'] = disciplinas
        professor['disciplina_ids'] = [disciplina['id'] for disciplina in disciplinas]
        professor['disciplinas_nomes'] = ', '.join(disciplina['nome'] for disciplina in disciplinas)

        primeira = disciplinas[0] if disciplinas else None
        professor['disciplina_nome'] = primeira['nome'] if primeira else professor.get('disciplina_nome')
        professor['disciplina_cor'] = primeira['cor'] if primeira else professor.get('disciplina_cor')

    return professores


def _anexar_vinculos(professores):
    return _anexar_cargas(_anexar_turmas(_anexar_disciplinas(professores)))


def criar_professor(escola_id, nome, disciplina_ids, max_aulas_semana, dias_disponiveis, turma_ids=None, cargas=None, cor=None):
    disciplina_ids = _normalizar_ids(disciplina_ids)
    if not disciplina_ids:
        return False, "Selecione pelo menos uma disciplina."

    conn = get_connection()
    try:
        dias_str = ','.join(dias_disponiveis) if isinstance(dias_disponiveis, list) else dias_disponiveis
        cursor = conn.execute(
            """INSERT INTO professores (escola_id, nome, cor, disciplina_id, max_aulas_semana, dias_disponiveis)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (escola_id, nome, _normalizar_cor(cor), disciplina_ids[0], max_aulas_semana, dias_str),
        )
        _sincronizar_disciplinas_professor(conn, cursor.lastrowid, escola_id, disciplina_ids)
        _sincronizar_turmas_professor(conn, cursor.lastrowid, escola_id, turma_ids)
        _sincronizar_cargas_professor(conn, cursor.lastrowid, escola_id, cargas)
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
        (escola_id,),
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        item['dias_lista'] = item['dias_disponiveis'].split(',')
        result.append(item)
    return _anexar_vinculos(result)


def buscar_professor(professor_id, escola_id=None):
    conn = get_connection()
    if escola_id is None:
        row = conn.execute(
            """SELECT p.*, d.nome AS disciplina_nome, d.cor AS disciplina_cor
               FROM professores p
               JOIN disciplinas d ON p.disciplina_id = d.id
               WHERE p.id = %s""",
            (professor_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT p.*, d.nome AS disciplina_nome, d.cor AS disciplina_cor
               FROM professores p
               JOIN disciplinas d ON p.disciplina_id = d.id
               WHERE p.id = %s AND p.escola_id = %s""",
            (professor_id, escola_id),
        ).fetchone()
    conn.close()

    if row:
        item = dict(row)
        item['dias_lista'] = item['dias_disponiveis'].split(',')
        return _anexar_vinculos([item])[0]
    return None


def atualizar_professor(professor_id, escola_id, nome, disciplina_ids, max_aulas_semana, dias_disponiveis, turma_ids=None, cargas=None, cor=None):
    disciplina_ids = _normalizar_ids(disciplina_ids)
    if not disciplina_ids:
        raise ValueError("Selecione pelo menos uma disciplina.")

    conn = get_connection()
    try:
        dias_str = ','.join(dias_disponiveis) if isinstance(dias_disponiveis, list) else dias_disponiveis
        conn.execute(
            """UPDATE professores
               SET nome = %s,
                   cor = %s,
                   disciplina_id = %s,
                   max_aulas_semana = %s,
                   dias_disponiveis = %s
               WHERE id = %s AND escola_id = %s""",
            (nome, _normalizar_cor(cor), disciplina_ids[0], max_aulas_semana, dias_str, professor_id, escola_id),
        )
        _sincronizar_disciplinas_professor(conn, professor_id, escola_id, disciplina_ids)
        _sincronizar_turmas_professor(conn, professor_id, escola_id, turma_ids)
        _sincronizar_cargas_professor(conn, professor_id, escola_id, cargas)
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
