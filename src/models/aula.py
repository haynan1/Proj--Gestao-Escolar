import logging
import time

import mysql.connector

from database.connection import get_connection
from models import regra_professor as _regras
from models.turno import normalizar_turno
from utils.conflitos import DIAS, PERIODOS

_logger = logging.getLogger(__name__)


MYSQL_RETRYABLE_LOCK_ERRORS = {1205, 1213}


def _is_retryable_lock_error(error):
    errno = getattr(error, 'errno', None)
    if errno in MYSQL_RETRYABLE_LOCK_ERRORS:
        return True
    if not isinstance(error, mysql.connector.Error):
        return False
    message = str(error).lower()
    return 'deadlock' in message or 'lock wait timeout' in message


def _is_duplicate_slot_error(error):
    """Violação de UNIQUE de slot (turma/professor): errno 1062."""
    return getattr(error, 'errno', None) == 1062


class ScheduleValidationError(ValueError):
    """Raised when schedule move payload is invalid."""


class ScheduleConflictError(ValueError):
    """Raised when a move would create a logical schedule conflict."""


def salvar_aulas(escola_id, aulas, turma_id=None, turno=None, max_retries=3):
    """Salva uma lista de aulas no banco. Cada aula é um dict com turma_id, professor_id, disciplina_id, dia, periodo."""
    turno = normalizar_turno(turno)
    tentativa = 0
    while True:
        conn = get_connection()
        try:
            if turma_id:
                conn.execute(
                    "DELETE FROM aulas WHERE escola_id = %s AND turno = %s AND turma_id = %s",
                    (escola_id, turno, turma_id),
                )
            else:
                conn.execute("DELETE FROM aulas WHERE escola_id = %s AND turno = %s", (escola_id, turno))
            for a in aulas:
                eh_vaga = 1 if a.get('vaga') else 0
                conn.execute(
                    """INSERT INTO aulas
                           (escola_id, turno, turma_id, professor_id, disciplina_id, dia, periodo, vaga, motivo_vaga)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        escola_id,
                        turno,
                        a['turma_id'],
                        a.get('professor_id') if not eh_vaga else None,
                        a.get('disciplina_id') if not eh_vaga else None,
                        a['dia'],
                        a['periodo'],
                        eh_vaga,
                        a.get('motivo_vaga') if eh_vaga else None,
                    ),
                )
            conn.commit()
            return
        except Exception as error:
            conn.rollback()
            if _is_duplicate_slot_error(error):
                raise ScheduleConflictError(
                    "Conflito de horário ao salvar a grade (slot já ocupado). "
                    "Tente gerar novamente."
                ) from error
            tentativa += 1
            if tentativa > max_retries or not _is_retryable_lock_error(error):
                raise
            time.sleep(0.15 * tentativa)
        finally:
            conn.close()


def listar_aulas(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, t.nome AS turma_nome, p.nome AS professor_nome,
                  p.cor AS professor_cor, p.dias_disponiveis,
                  d.nome AS disciplina_nome, d.cor AS disciplina_cor
           FROM aulas a
           JOIN turmas t ON a.turma_id = t.id AND t.turno = a.turno
           LEFT JOIN professores p ON a.professor_id = p.id AND p.turno = a.turno
           LEFT JOIN disciplinas d ON a.disciplina_id = d.id AND d.turno = a.turno
           WHERE a.escola_id = %s AND a.turno = %s
           ORDER BY a.turma_id, a.dia, a.periodo""",
        (escola_id, turno)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def limpar_aulas(escola_id, turma_id=None, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        if turma_id:
            conn.execute(
                "DELETE FROM aulas WHERE escola_id = %s AND turno = %s AND turma_id = %s",
                (escola_id, turno, turma_id),
            )
        else:
            conn.execute("DELETE FROM aulas WHERE escola_id = %s AND turno = %s", (escola_id, turno))
        conn.commit()
    except Exception:
        conn.rollback()
        _logger.exception('Erro ao limpar aulas da escola %s turma %s.', escola_id, turma_id)
        raise
    finally:
        conn.close()


def deletar_aula(aula_id, escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        aula = conn.execute(
            """SELECT a.*, t.nome AS turma_nome, p.nome AS professor_nome,
                      p.cor AS professor_cor, p.dias_disponiveis,
                      d.nome AS disciplina_nome, d.cor AS disciplina_cor
               FROM aulas a
               JOIN turmas t ON a.turma_id = t.id AND t.turno = a.turno
               LEFT JOIN professores p ON a.professor_id = p.id AND p.turno = a.turno
               LEFT JOIN disciplinas d ON a.disciplina_id = d.id AND d.turno = a.turno
               WHERE a.id = %s AND a.escola_id = %s AND a.turno = %s""",
            (aula_id, escola_id, turno),
        ).fetchone()
        if not aula:
            return None

        cursor = conn.execute(
            "DELETE FROM aulas WHERE id = %s AND escola_id = %s AND turno = %s",
            (aula_id, escola_id, turno),
        )
        conn.commit()
        return dict(aula) if cursor.rowcount > 0 else None
    except Exception:
        conn.rollback()
        _logger.exception('Erro inesperado ao deletar aula %s da escola %s.', aula_id, escola_id)
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


def _validar_regras_professor(conn, professor_id, turma_id, disciplina_id, dia, periodo,
                              aulas_por_dia, ignorar_aula_ids=None):
    """Aplica à edição manual as mesmas regras obrigatórias que o solver respeita.

    Sem isto, a grade sai da geração respeitando as regras e o primeiro arrasto as
    desfaz em silêncio. A tradução regra -> slot é a de models.regra_professor, a
    mesma consumida por solver.horario_cpsat.

    Ficam de fora, por não serem decidíveis num movimento isolado:
    - AULA_GEMINADA, que exige um mínimo de blocos (mover uma aula não viola mínimo);
    - o alvo exato de CONTAGEM_POR_DIA, cujo estado intermediário é legítimo enquanto
      o usuário reorganiza a grade (a restrição de DIA dessa regra é aplicada).
    """
    if not professor_id:
        return

    regras = _regras.regras_aplicaveis(
        _regras.carregar_regras_professor(conn, professor_id), disciplina_id
    )
    if not regras:
        return

    periodo = int(periodo)
    periodos_turma = list(range(1, int(aulas_por_dia or 5) + 1))

    bloqueio = _regras.regra_que_bloqueia_slot(regras, dia, periodo, periodos_turma)
    if bloqueio:
        raise ScheduleConflictError(
            f"Uma regra do professor impede este horário: {_regras.descrever_regra(bloqueio)}."
        )

    ignorar = {int(item) for item in (ignorar_aula_ids or []) if item is not None}
    _validar_max_aulas_dia(conn, regras, turma_id, disciplina_id, dia, ignorar)
    _validar_dias_ocupados(conn, regras, professor_id, dia, ignorar)


def _validar_max_aulas_dia(conn, regras, turma_id, disciplina_id, dia, ignorar):
    """MAX_AULAS_DIA: limita aulas da mesma turma+disciplina no dia (espalha a matéria)."""
    limites = [
        int((r.get('parametros') or {}).get('quantidade') or 0)
        for r in regras
        if r.get('tipo') == _regras.MAX_AULAS_DIA and r.get('obrigatoria')
    ]
    limites = [n for n in limites if n > 0]
    if not limites:
        return

    rows = conn.execute(
        """SELECT id FROM aulas
           WHERE turma_id = %s AND disciplina_id = %s AND dia = %s""",
        (turma_id, disciplina_id, dia),
    ).fetchall()
    no_dia = sum(1 for row in rows if int(row['id']) not in ignorar) + 1

    menor = min(limites)
    if no_dia > menor:
        raise ScheduleConflictError(
            f"Uma regra do professor permite no máximo {menor} aula(s) desta disciplina por dia."
        )


def _validar_dias_ocupados(conn, regras, professor_id, dia, ignorar):
    """DIA_LIVRE / DISTRIBUIR_EM_N_DIAS: limitam em quantos dias o professor trabalha."""
    limites = []
    for regra in regras:
        if not regra.get('obrigatoria'):
            continue
        quantidade = int((regra.get('parametros') or {}).get('quantidade') or 0)
        if regra.get('tipo') == _regras.DIA_LIVRE and quantidade > 0:
            limites.append((len(DIAS) - quantidade, regra))
        elif regra.get('tipo') == _regras.DISTRIBUIR_EM_N_DIAS and quantidade > 0:
            limites.append((quantidade, regra))
    if not limites:
        return

    rows = conn.execute(
        "SELECT id, dia FROM aulas WHERE professor_id = %s",
        (professor_id,),
    ).fetchall()
    dias_usados = {row['dia'] for row in rows if int(row['id']) not in ignorar}
    dias_usados.add(dia)

    for limite, regra in limites:
        if len(dias_usados) > limite:
            raise ScheduleConflictError(
                f"Uma regra do professor seria quebrada: {_regras.descrever_regra(regra)}."
            )


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


def criar_aula_manual(escola_id, turma_id, professor_id, disciplina_id, dia, periodo, turno=None):
    turno = normalizar_turno(turno)
    if dia not in DIAS:
        raise ScheduleValidationError("Dia inválido para a grade horária.")

    conn = get_connection()
    try:
        turma = conn.execute(
            """SELECT id, COALESCE(aulas_por_dia, 5) AS aulas_por_dia
               FROM turmas
               WHERE id = %s AND escola_id = %s AND turno = %s""",
            (turma_id, escola_id, turno),
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
                 AND p.turno = %s
                 AND t.turno = %s
                 AND d.turno = %s
                 AND pc.professor_id = %s
                 AND pc.turma_id = %s
                 AND pc.disciplina_id = %s""",
            (escola_id, escola_id, escola_id, turno, turno, turno, professor_id, turma_id, disciplina_id),
        ).fetchone()
        if not carga:
            raise ScheduleValidationError("Este professor não possui aulas cadastradas para esta turma e disciplina.")

        _validar_disponibilidade_professor(conn, escola_id, professor_id, dia)
        _validar_limite_professor(conn, escola_id, professor_id)
        _validar_regras_professor(conn, professor_id, turma_id, disciplina_id, dia, periodo,
                                  turma.get('aulas_por_dia'))
        _validar_aulas_seguidas_disciplina(conn, escola_id, turma_id, disciplina_id, dia, periodo)

        aula_turma = conn.execute(
            """SELECT id, vaga FROM aulas
               WHERE escola_id = %s AND turma_id = %s AND dia = %s AND periodo = %s""",
            (escola_id, turma_id, dia, periodo),
        ).fetchone()
        if aula_turma:
            if aula_turma.get('vaga'):
                # Slot ocupado por uma VAGA: preenche substituindo-a.
                conn.execute("DELETE FROM aulas WHERE id = %s", (aula_turma['id'],))
            else:
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
            """INSERT INTO aulas (escola_id, turno, turma_id, professor_id, disciplina_id, dia, periodo)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (escola_id, turno, turma_id, professor_id, disciplina_id, dia, periodo),
        )
        conn.commit()
        return cursor.lastrowid
    except (ScheduleConflictError, ScheduleValidationError):
        conn.rollback()
        raise
    except Exception as error:
        conn.rollback()
        if _is_duplicate_slot_error(error):
            raise ScheduleConflictError("Este horário acabou de ser ocupado. Tente novamente.") from error
        _logger.exception('Erro inesperado ao criar aula manual na escola %s.', escola_id)
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
                      a.vaga,
                      COALESCE(t.aulas_por_dia, 5) AS aulas_por_dia
               FROM aulas a
               JOIN turmas t ON t.id = a.turma_id
               WHERE a.id = %s""",
            (aula_id,),
        ).fetchone()

        if not aula_atual:
            raise ScheduleValidationError("Aula não encontrada.")
        if aula_atual.get('vaga'):
            raise ScheduleValidationError("Não é possível mover uma vaga.")
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
                      periodo,
                      vaga
               FROM aulas
               WHERE turma_id = %s AND dia = %s AND periodo = %s AND id <> %s""",
            (aula_atual['turma_id'], novo_dia, novo_periodo, aula_id),
        ).fetchone()

        # Soltar sobre uma VAGA: remove a vaga e faz um move simples para o slot livre.
        if aula_destino and aula_destino.get('vaga'):
            conn.execute("DELETE FROM aulas WHERE id = %s", (aula_destino['id'],))
            aula_destino = None

        if aula_destino:
            # Na troca as duas aulas mudam de lugar: cada uma é validada no slot que
            # vai ocupar, ignorando o par para não conflitarem consigo mesmas.
            par = [aula_atual['id'], aula_destino['id']]
            _validar_regras_professor(
                conn, aula_atual['professor_id'], aula_atual['turma_id'],
                aula_atual['disciplina_id'], novo_dia, novo_periodo,
                aula_atual.get('aulas_por_dia'), ignorar_aula_ids=par,
            )
            _validar_aulas_seguidas_disciplina(
                conn,
                aula_atual['escola_id'],
                aula_atual['turma_id'],
                aula_atual['disciplina_id'],
                novo_dia,
                novo_periodo,
                ignorar_aula_ids=par,
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
            _validar_regras_professor(
                conn, aula_destino['professor_id'], aula_atual['turma_id'],
                aula_destino['disciplina_id'], aula_atual['dia'], aula_atual['periodo'],
                aula_atual.get('aulas_por_dia'), ignorar_aula_ids=par,
            )
            _validar_aulas_seguidas_disciplina(
                conn,
                aula_atual['escola_id'],
                aula_atual['turma_id'],
                aula_destino['disciplina_id'],
                aula_atual['dia'],
                aula_atual['periodo'],
                ignorar_aula_ids=par,
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

        _validar_regras_professor(
            conn, aula_atual['professor_id'], aula_atual['turma_id'],
            aula_atual['disciplina_id'], novo_dia, novo_periodo,
            aula_atual.get('aulas_por_dia'), ignorar_aula_ids=[aula_atual['id']],
        )
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
    except (ScheduleConflictError, ScheduleValidationError):
        conn.rollback()
        raise
    except Exception as error:
        conn.rollback()
        if _is_duplicate_slot_error(error):
            raise ScheduleConflictError("Este horário acabou de ser ocupado. Tente novamente.") from error
        _logger.exception('Erro inesperado ao mover aula %s para %s/%s.', aula_id, novo_dia, novo_periodo)
        raise
    finally:
        conn.close()


def deletar_aulas_escola(escola_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM aulas WHERE escola_id = %s", (escola_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        _logger.exception('Erro ao deletar aulas da escola %s.', escola_id)
        raise
    finally:
        conn.close()
