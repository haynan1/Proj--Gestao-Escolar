from datetime import date, datetime

from database.connection import get_connection
from models.turno import normalizar_turno


TIPOS_OCORRENCIA = {
    'falta': 'Falta',
    'ocorrencia': 'Ocorrência',
}


class RelatorioProfessorValidationError(ValueError):
    """Raised when a teacher report payload is invalid."""


def _parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError) as exc:
        raise RelatorioProfessorValidationError('Informe uma data válida.') from exc


def _parse_month(value):
    try:
        parsed = datetime.strptime(str(value), '%Y-%m')
    except (TypeError, ValueError) as exc:
        raise RelatorioProfessorValidationError('Informe um mês válido.') from exc

    inicio = parsed.date().replace(day=1)
    if inicio.month == 12:
        fim = inicio.replace(year=inicio.year + 1, month=1, day=1)
    else:
        fim = inicio.replace(month=inicio.month + 1, day=1)
    return inicio, fim


def listar_relatorios_professores(escola_id, turno=None, mes=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        params = [escola_id, turno]
        filtro_mes = ''
        if mes:
            inicio, fim = _parse_month(mes)
            filtro_mes = ' AND rp.data_ocorrencia >= %s AND rp.data_ocorrencia < %s'
            params.extend([inicio, fim])

        rows = conn.execute(
            f"""SELECT rp.*,
                       COALESCE(p.nome, NULLIF(rp.professor_nome_snapshot, ''), 'Professor removido') AS professor_nome,
                       COALESCE(p.cor, rp.professor_cor_snapshot) AS professor_cor,
                       criador.nome AS criado_por_nome
                FROM relatorios_professores rp
                LEFT JOIN professores p ON p.id = rp.professor_id
                LEFT JOIN usuarios criador ON criador.id = rp.criado_por_usuario_id
                WHERE rp.escola_id = %s
                  AND rp.turno = %s
                  AND rp.excluido_em IS NULL
                  {filtro_mes}
                ORDER BY rp.data_ocorrencia DESC, rp.criado_em DESC, rp.id DESC""",
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def criar_relatorio_professor(
    escola_id,
    turno,
    professor_id,
    data_ocorrencia,
    tipo,
    descricao,
    criado_por_usuario_id=None,
):
    turno = normalizar_turno(turno)
    data_ocorrencia = _parse_date(data_ocorrencia)
    tipo = (tipo or '').strip().lower()
    descricao = (descricao or '').strip()

    if tipo not in TIPOS_OCORRENCIA:
        raise RelatorioProfessorValidationError('Selecione o tipo do registro.')
    if not descricao:
        raise RelatorioProfessorValidationError('Descreva a falta ou ocorrência.')

    try:
        professor_id = int(professor_id)
    except (TypeError, ValueError) as exc:
        raise RelatorioProfessorValidationError('Selecione um professor válido.') from exc

    conn = get_connection()
    try:
        professor = conn.execute(
            """SELECT id, nome, cor
               FROM professores
               WHERE id = %s AND escola_id = %s AND turno = %s""",
            (professor_id, escola_id, turno),
        ).fetchone()
        if not professor:
            raise RelatorioProfessorValidationError('Professor não encontrado para este turno.')

        cursor = conn.execute(
            """INSERT INTO relatorios_professores (
                   escola_id,
                   turno,
                   professor_id,
                   professor_nome_snapshot,
                   professor_cor_snapshot,
                   data_ocorrencia,
                   tipo,
                   descricao,
                   criado_por_usuario_id
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                escola_id,
                turno,
                professor_id,
                professor['nome'],
                professor.get('cor'),
                data_ocorrencia,
                tipo,
                descricao,
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


def deletar_relatorio_professor(relatorio_id, escola_id, turno=None, excluido_por_usuario_id=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        cursor = conn.execute(
            """UPDATE relatorios_professores
               SET excluido_em = CURRENT_TIMESTAMP,
                   excluido_por_usuario_id = %s
               WHERE id = %s
                 AND escola_id = %s
                 AND turno = %s
                 AND excluido_em IS NULL""",
            (
                int(excluido_por_usuario_id) if excluido_por_usuario_id else None,
                relatorio_id,
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
