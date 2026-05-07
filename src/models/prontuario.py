from datetime import date, datetime

from database.connection import get_connection
from models.turno import normalizar_turno


PRIORIDADES_PRONTUARIO = {
    'baixa': 'Acompanhar',
    'media': 'Atenção',
    'alta': 'Prioritário',
}

STATUS_PRONTUARIO = {
    'aberto': 'Aberto',
    'em_acompanhamento': 'Em acompanhamento',
    'resolvido': 'Resolvido',
}


class ProntuarioValidationError(ValueError):
    """Raised when a student record payload is invalid."""


def _parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError) as exc:
        raise ProntuarioValidationError('Informe uma data valida.') from exc


def _normalizar_prioridade(value):
    prioridade = (value or 'media').strip().lower()
    return prioridade if prioridade in PRIORIDADES_PRONTUARIO else 'media'


def _normalizar_status(value):
    status = (value or 'aberto').strip().lower()
    return status if status in STATUS_PRONTUARIO else 'aberto'


def listar_prontuarios(escola_id, turno=None, status=None):
    turno = normalizar_turno(turno)
    status = (status or '').strip().lower()
    filtro_status = ''
    params = [escola_id, turno]
    if status in STATUS_PRONTUARIO:
        filtro_status = ' AND pr.status = %s'
        params.append(status)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""SELECT pr.*,
                       t.nome AS turma_nome,
                       p.nome AS professor_nome,
                       p.cor AS professor_cor,
                       criador.nome AS criado_por_nome,
                       feedback_usuario.nome AS feedback_por_nome
                FROM prontuarios_alunos pr
                JOIN turmas t ON t.id = pr.turma_id
                LEFT JOIN professores p ON p.id = pr.professor_marcado_id
                LEFT JOIN usuarios criador ON criador.id = pr.criado_por_usuario_id
                LEFT JOIN usuarios feedback_usuario ON feedback_usuario.id = pr.feedback_por_usuario_id
                WHERE pr.escola_id = %s
                  AND pr.turno = %s
                  AND pr.excluido_em IS NULL
                  {filtro_status}
                ORDER BY pr.status = 'resolvido', pr.data_registro DESC, pr.criado_em DESC, pr.id DESC""",
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def criar_prontuario(
    escola_id,
    turno,
    aluno_nome,
    turma_id,
    observacao,
    professor_marcado_id=None,
    prioridade='media',
    criado_por_usuario_id=None,
    data_registro=None,
):
    turno = normalizar_turno(turno)
    aluno_nome = (aluno_nome or '').strip()
    observacao = (observacao or '').strip()
    prioridade = _normalizar_prioridade(prioridade)
    data_registro = _parse_date(data_registro or date.today().isoformat())

    if not aluno_nome:
        raise ProntuarioValidationError('Informe o nome do aluno.')
    if not observacao:
        raise ProntuarioValidationError('Descreva o ponto de atenção.')

    try:
        turma_id = int(turma_id)
    except (TypeError, ValueError) as exc:
        raise ProntuarioValidationError('Selecione uma turma valida.') from exc

    professor_id = None
    if professor_marcado_id:
        try:
            professor_id = int(professor_marcado_id)
        except (TypeError, ValueError) as exc:
            raise ProntuarioValidationError('Selecione um professor valido.') from exc

    conn = get_connection()
    try:
        turma = conn.execute(
            "SELECT id FROM turmas WHERE id = %s AND escola_id = %s AND turno = %s",
            (turma_id, escola_id, turno),
        ).fetchone()
        if not turma:
            raise ProntuarioValidationError('Turma nao encontrada para este turno.')

        if professor_id:
            professor = conn.execute(
                "SELECT id FROM professores WHERE id = %s AND escola_id = %s AND turno = %s",
                (professor_id, escola_id, turno),
            ).fetchone()
            if not professor:
                raise ProntuarioValidationError('Professor nao encontrado para este turno.')

        cursor = conn.execute(
            """INSERT INTO prontuarios_alunos (
                   escola_id,
                   turno,
                   aluno_nome,
                   turma_id,
                   professor_marcado_id,
                   prioridade,
                   status,
                   observacao,
                   data_registro,
                   criado_por_usuario_id
               ) VALUES (%s, %s, %s, %s, %s, %s, 'aberto', %s, %s, %s)""",
            (
                escola_id,
                turno,
                aluno_nome,
                turma_id,
                professor_id,
                prioridade,
                observacao,
                data_registro,
                int(criado_por_usuario_id) if criado_por_usuario_id else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def registrar_feedback_prontuario(
    prontuario_id,
    escola_id,
    turno,
    feedback,
    status='em_acompanhamento',
    feedback_por_usuario_id=None,
):
    turno = normalizar_turno(turno)
    feedback = (feedback or '').strip()
    status = _normalizar_status(status)

    if not feedback:
        raise ProntuarioValidationError('Escreva um feedback antes de salvar.')

    conn = get_connection()
    try:
        cursor = conn.execute(
            """UPDATE prontuarios_alunos
               SET feedback = %s,
                   status = %s,
                   feedback_por_usuario_id = %s,
                   feedback_em = CURRENT_TIMESTAMP
               WHERE id = %s
                 AND escola_id = %s
                 AND turno = %s
                 AND excluido_em IS NULL""",
            (
                feedback,
                status,
                int(feedback_por_usuario_id) if feedback_por_usuario_id else None,
                prontuario_id,
                escola_id,
                turno,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def arquivar_prontuario(prontuario_id, escola_id, turno=None, excluido_por_usuario_id=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        cursor = conn.execute(
            """UPDATE prontuarios_alunos
               SET excluido_em = CURRENT_TIMESTAMP,
                   excluido_por_usuario_id = %s
               WHERE id = %s
                 AND escola_id = %s
                 AND turno = %s
                 AND excluido_em IS NULL""",
            (
                int(excluido_por_usuario_id) if excluido_por_usuario_id else None,
                prontuario_id,
                escola_id,
                turno,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
