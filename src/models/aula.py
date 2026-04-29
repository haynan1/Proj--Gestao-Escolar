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

        aula_destino = conn.execute(
            """SELECT id,
                      professor_id,
                      dia,
                      periodo
               FROM aulas
               WHERE turma_id = %s AND dia = %s AND periodo = %s AND id <> %s""",
            (aula_atual['turma_id'], novo_dia, novo_periodo, aula_id),
        ).fetchone()

        if aula_destino:
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
                raise ScheduleConflictError("O professor da aula arrastada ja possui aula nesse horario.")

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
                raise ScheduleConflictError("O professor da aula de destino ja possui aula no horario de origem.")

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
