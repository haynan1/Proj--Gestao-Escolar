from database.connection import get_connection
from utils.conflitos import DIAS, PERIODOS


class ScheduleValidationError(ValueError):
    """Raised when schedule move payload is invalid."""


class ScheduleConflictError(ValueError):
    """Raised when a move would create a logical schedule conflict."""


def salvar_aulas(escola_id, aulas, turma_id=None):
    """Salva uma lista de aulas no banco. Cada aula é um dict com turma_id, professor_id, disciplina_id, dia, periodo."""
    conn = get_connection()
    try:
        if turma_id:
            conn.execute("DELETE FROM aulas WHERE escola_id = %s AND turma_id = %s", (escola_id, turma_id))
        else:
            conn.execute("DELETE FROM aulas WHERE escola_id = %s", (escola_id,))
        for a in aulas:
            conn.execute(
                """INSERT INTO aulas (escola_id, turma_id, professor_id, disciplina_id, dia, periodo)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (escola_id, a['turma_id'], a['professor_id'], a['disciplina_id'], a['dia'], a['periodo'])
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_aulas(escola_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, t.nome AS turma_nome, p.nome AS professor_nome,
                  p.cor AS professor_cor,
                  d.nome AS disciplina_nome, d.cor AS disciplina_cor
           FROM aulas a
           JOIN turmas t ON a.turma_id = t.id
           JOIN professores p ON a.professor_id = p.id
           JOIN disciplinas d ON a.disciplina_id = d.id
           WHERE a.escola_id = %s
           ORDER BY a.turma_id, a.dia, a.periodo""",
        (escola_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def limpar_aulas(escola_id, turma_id=None):
    conn = get_connection()
    try:
        if turma_id:
            conn.execute(
                "DELETE FROM aulas WHERE escola_id = %s AND turma_id = %s",
                (escola_id, turma_id),
            )
        else:
            conn.execute("DELETE FROM aulas WHERE escola_id = %s", (escola_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _dias_disponiveis_professor(row):
    if not row:
        return []
    return [
        item.strip()
        for item in (row['dias_disponiveis'] or '').split(',')
        if item.strip()
    ]


def _validar_disponibilidade_professor(conn, escola_id, professor_id, dia):
    professor = conn.execute(
        "SELECT dias_disponiveis FROM professores WHERE id = %s AND escola_id = %s",
        (professor_id, escola_id),
    ).fetchone()
    dias_disponiveis = _dias_disponiveis_professor(professor)
    if dias_disponiveis and dia not in dias_disponiveis:
        raise ScheduleConflictError("O professor não está disponível neste dia.")


def _validar_limite_professor(conn, escola_id, professor_id):
    professor = conn.execute(
        "SELECT COALESCE(max_aulas_semana, 0) AS max_aulas_semana FROM professores WHERE id = %s AND escola_id = %s",
        (professor_id, escola_id),
    ).fetchone()
    max_aulas_semana = int((professor or {}).get('max_aulas_semana') or 0)
    if max_aulas_semana <= 0:
        return

    aulas_professor = conn.execute(
        "SELECT COUNT(*) AS total FROM aulas WHERE escola_id = %s AND professor_id = %s",
        (escola_id, professor_id),
    ).fetchone()
    if aulas_professor and int(aulas_professor['total'] or 0) >= max_aulas_semana:
        raise ScheduleConflictError("O professor já atingiu o limite semanal de aulas.")


def _validar_aulas_seguidas_disciplina(conn, escola_id, turma_id, disciplina_id, dia, periodo, ignorar_aula_ids=None):
    ignorar = {int(aula_id) for aula_id in (ignorar_aula_ids or []) if aula_id is not None}
    rows = conn.execute(
        """SELECT id, periodo
           FROM aulas
           WHERE escola_id = %s
             AND turma_id = %s
             AND disciplina_id = %s
             AND dia = %s""",
        (escola_id, turma_id, disciplina_id, dia),
    ).fetchall()

    periodos = {
        int(row['periodo'])
        for row in rows
        if int(row['id']) not in ignorar
    }
    periodos.add(int(periodo))

    for inicio in range(int(periodo) - 2, int(periodo) + 1):
        if inicio < 1:
            continue
        if all(p in periodos for p in (inicio, inicio + 1, inicio + 2)):
            raise ScheduleConflictError("A regra de no máximo 2 aulas seguidas da mesma disciplina seria quebrada.")


def criar_aula_manual(escola_id, turma_id, professor_id, disciplina_id, dia, periodo):
    if dia not in DIAS:
        raise ScheduleValidationError("Dia inválido para a grade horária.")

    conn = get_connection()
    try:
        turma = conn.execute(
            "SELECT id, COALESCE(aulas_por_dia, 5) AS aulas_por_dia FROM turmas WHERE id = %s AND escola_id = %s",
            (turma_id, escola_id),
        ).fetchone()
        if not turma:
            raise ScheduleValidationError("Turma não encontrada.")
        if periodo not in PERIODOS or periodo > int(turma.get('aulas_por_dia') or 5):
            raise ScheduleValidationError("Período inválido para a grade desta turma.")

        carga = conn.execute(
            """SELECT pc.aulas_semana
               FROM professores_cargas pc
               JOIN professores p ON p.id = pc.professor_id
               JOIN turmas t ON t.id = pc.turma_id
               JOIN disciplinas d ON d.id = pc.disciplina_id
               WHERE p.escola_id = %s
                 AND t.escola_id = %s
                 AND d.escola_id = %s
                 AND pc.professor_id = %s
                 AND pc.turma_id = %s
                 AND pc.disciplina_id = %s""",
            (escola_id, escola_id, escola_id, professor_id, turma_id, disciplina_id),
        ).fetchone()
        if not carga:
            raise ScheduleValidationError("Este professor não possui aulas cadastradas para esta turma e disciplina.")

        _validar_disponibilidade_professor(conn, escola_id, professor_id, dia)
        _validar_limite_professor(conn, escola_id, professor_id)
        _validar_aulas_seguidas_disciplina(conn, escola_id, turma_id, disciplina_id, dia, periodo)

        aula_turma = conn.execute(
            """SELECT id FROM aulas
               WHERE escola_id = %s AND turma_id = %s AND dia = %s AND periodo = %s""",
            (escola_id, turma_id, dia, periodo),
        ).fetchone()
        if aula_turma:
            raise ScheduleConflictError("A turma já possui aula neste horário.")

        aula_professor = conn.execute(
            """SELECT id FROM aulas
               WHERE escola_id = %s AND professor_id = %s AND dia = %s AND periodo = %s""",
            (escola_id, professor_id, dia, periodo),
        ).fetchone()
        if aula_professor:
            raise ScheduleConflictError("O professor já possui aula neste horário.")

        aulas_existentes = conn.execute(
            """SELECT COUNT(*) AS total
               FROM aulas
               WHERE escola_id = %s
                 AND turma_id = %s
                 AND professor_id = %s
                 AND disciplina_id = %s""",
            (escola_id, turma_id, professor_id, disciplina_id),
        ).fetchone()
        if aulas_existentes and int(aulas_existentes['total'] or 0) >= int(carga['aulas_semana'] or 0):
            raise ScheduleConflictError("As aulas cadastradas para este professor já foram preenchidas.")

        cursor = conn.execute(
            """INSERT INTO aulas (escola_id, turma_id, professor_id, disciplina_id, dia, periodo)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (escola_id, turma_id, professor_id, disciplina_id, dia, periodo),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mover_aula(aula_id, novo_dia, novo_periodo, escola_id=None):
    """Move uma aula para outro dia/periodo ou troca com a aula do destino."""
    if novo_dia not in DIAS:
        raise ScheduleValidationError("Dia inválido para a grade horária.")
    conn = get_connection()
    try:
        aula_atual = conn.execute(
            """SELECT a.id,
                      a.escola_id,
                      a.turma_id,
                      a.professor_id,
                      a.disciplina_id,
                      a.dia,
                      a.periodo,
                      COALESCE(t.aulas_por_dia, 5) AS aulas_por_dia
               FROM aulas a
               JOIN turmas t ON t.id = a.turma_id
               WHERE a.id = %s""",
            (aula_id,),
        ).fetchone()

        if not aula_atual:
            raise ScheduleValidationError("Aula não encontrada.")
        if escola_id is not None and aula_atual['escola_id'] != escola_id:
            raise ScheduleValidationError("A aula informada não pertence a esta escola.")
        if novo_periodo not in PERIODOS or novo_periodo > int(aula_atual.get('aulas_por_dia') or 5):
            raise ScheduleValidationError("Período inválido para a grade desta turma.")

        _validar_disponibilidade_professor(conn, aula_atual['escola_id'], aula_atual['professor_id'], novo_dia)

        aula_destino = conn.execute(
            """SELECT id,
                      professor_id,
                      disciplina_id,
                      dia,
                      periodo
               FROM aulas
               WHERE turma_id = %s AND dia = %s AND periodo = %s AND id <> %s""",
            (aula_atual['turma_id'], novo_dia, novo_periodo, aula_id),
        ).fetchone()

        if aula_destino:
            _validar_aulas_seguidas_disciplina(
                conn,
                aula_atual['escola_id'],
                aula_atual['turma_id'],
                aula_atual['disciplina_id'],
                novo_dia,
                novo_periodo,
                ignorar_aula_ids=[aula_atual['id'], aula_destino['id']],
            )

            conflito_professor_atual = conn.execute(
                """SELECT id
                   FROM aulas
                   WHERE professor_id = %s
                     AND dia = %s
                     AND periodo = %s
                     AND id NOT IN (%s, %s)""",
                (
                    aula_atual['professor_id'],
                    novo_dia,
                    novo_periodo,
                    aula_atual['id'],
                    aula_destino['id'],
                ),
            ).fetchone()
            if conflito_professor_atual:
                raise ScheduleConflictError("O professor da aula arrastada já possui aula nesse horário.")

            conflito_professor_destino = conn.execute(
                """SELECT id
                   FROM aulas
                   WHERE professor_id = %s
                     AND dia = %s
                     AND periodo = %s
                     AND id NOT IN (%s, %s)""",
                (
                    aula_destino['professor_id'],
                    aula_atual['dia'],
                    aula_atual['periodo'],
                    aula_atual['id'],
                    aula_destino['id'],
                ),
            ).fetchone()
            if conflito_professor_destino:
                raise ScheduleConflictError("O professor da aula de destino já possui aula no horário de origem.")

            _validar_disponibilidade_professor(
                conn,
                aula_atual['escola_id'],
                aula_destino['professor_id'],
                aula_atual['dia'],
            )
            _validar_aulas_seguidas_disciplina(
                conn,
                aula_atual['escola_id'],
                aula_atual['turma_id'],
                aula_destino['disciplina_id'],
                aula_atual['dia'],
                aula_atual['periodo'],
                ignorar_aula_ids=[aula_atual['id'], aula_destino['id']],
            )

            conn.execute(
                "UPDATE aulas SET dia = %s, periodo = %s WHERE id = %s",
                ('__troca__', -int(aula_destino['id']), aula_destino['id']),
            )
            conn.execute(
                "UPDATE aulas SET dia = %s, periodo = %s WHERE id = %s",
                (novo_dia, novo_periodo, aula_atual['id']),
            )
            conn.execute(
                "UPDATE aulas SET dia = %s, periodo = %s WHERE id = %s",
                (aula_atual['dia'], aula_atual['periodo'], aula_destino['id']),
            )
            conn.commit()
            return {
                'action': 'swap',
                'swapped_aula_id': aula_destino['id'],
            }

        conflito_professor = conn.execute(
            """SELECT id
               FROM aulas
               WHERE professor_id = %s AND dia = %s AND periodo = %s AND id <> %s""",
            (aula_atual['professor_id'], novo_dia, novo_periodo, aula_id),
        ).fetchone()
        if conflito_professor:
            raise ScheduleConflictError("O professor já possui uma aula nesse dia e período.")

        _validar_aulas_seguidas_disciplina(
            conn,
            aula_atual['escola_id'],
            aula_atual['turma_id'],
            aula_atual['disciplina_id'],
            novo_dia,
            novo_periodo,
            ignorar_aula_ids=[aula_atual['id']],
        )

        conn.execute(
            "UPDATE aulas SET dia = %s, periodo = %s WHERE id = %s",
            (novo_dia, novo_periodo, aula_id)
        )
        conn.commit()
        return {'action': 'move'}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_aulas_escola(escola_id):
    conn = get_connection()
    conn.execute("DELETE FROM aulas WHERE escola_id = %s", (escola_id,))
    conn.commit()
    conn.close()
