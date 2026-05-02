from datetime import date, datetime

from database.connection import get_connection
from models.turno import normalizar_turno
from utils.conflitos import DIAS, PERIODOS


class HorarioTemporarioValidationError(ValueError):
    """Raised when a temporary schedule payload is invalid."""


def _parse_date(value, field_name):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise HorarioTemporarioValidationError(f"{field_name} invalida.") from exc


def listar_horarios_temporarios(escola_id, turno=None, turma_id=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        params = [escola_id, turno]
        filtro_turma = ""
        if turma_id:
            filtro_turma = " AND ht.turma_id = %s"
            params.append(turma_id)

        rows = conn.execute(
            f"""SELECT ht.*,
                       t.nome AS turma_nome,
                       p.nome AS professor_nome,
                       p.cor AS professor_cor,
                       d.nome AS disciplina_nome,
                       d.cor AS disciplina_cor
                FROM horarios_temporarios ht
                JOIN turmas t ON t.id = ht.turma_id
                LEFT JOIN professores p ON p.id = ht.professor_id
                LEFT JOIN disciplinas d ON d.id = ht.disciplina_id
                WHERE ht.escola_id = %s
                  AND ht.turno = %s
                  {filtro_turma}
                ORDER BY ht.data_inicio DESC, ht.data_fim DESC, ht.dia, ht.periodo""",
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def listar_grupos_horarios_temporarios(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT titulo,
                      data_inicio,
                      data_fim,
                      dia,
                      observacao,
                      COUNT(*) AS total_aulas,
                      COUNT(DISTINCT turma_id) AS total_turmas,
                      MIN(criado_em) AS criado_em
               FROM horarios_temporarios
               WHERE escola_id = %s
                 AND turno = %s
               GROUP BY titulo, data_inicio, data_fim, dia, observacao
               ORDER BY data_inicio DESC, data_fim DESC, dia, titulo""",
            (escola_id, turno),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def criar_horario_temporario(
    escola_id,
    turno,
    turma_id,
    data_inicio,
    data_fim,
    dia,
    periodo,
    titulo,
    professor_id=None,
    disciplina_id=None,
    observacao=None,
):
    turno = normalizar_turno(turno)
    data_inicio = _parse_date(data_inicio, "Data inicial")
    data_fim = _parse_date(data_fim or data_inicio, "Data final")

    if data_fim < data_inicio:
        raise HorarioTemporarioValidationError("A data final nao pode ser anterior a data inicial.")
    if dia not in DIAS:
        raise HorarioTemporarioValidationError("Dia invalido.")
    try:
        turma_id = int(turma_id)
        periodo = int(periodo)
    except (TypeError, ValueError) as exc:
        raise HorarioTemporarioValidationError("Turma e periodo devem ser validos.") from exc
    if periodo not in PERIODOS:
        raise HorarioTemporarioValidationError("Periodo invalido.")

    titulo = (titulo or "").strip()
    observacao = (observacao or "").strip() or None
    if not titulo:
        raise HorarioTemporarioValidationError("Informe um titulo para o horario temporario.")

    professor_id = int(professor_id) if professor_id else None
    disciplina_id = int(disciplina_id) if disciplina_id else None

    conn = get_connection()
    try:
        turma = conn.execute(
            """SELECT id, COALESCE(aulas_por_dia, 5) AS aulas_por_dia
               FROM turmas
               WHERE id = %s AND escola_id = %s AND turno = %s""",
            (turma_id, escola_id, turno),
        ).fetchone()
        if not turma:
            raise HorarioTemporarioValidationError("Turma nao encontrada.")
        if periodo > int(turma.get("aulas_por_dia") or 5):
            raise HorarioTemporarioValidationError("Periodo invalido para a turma.")

        if professor_id:
            professor = conn.execute(
                "SELECT id FROM professores WHERE id = %s AND escola_id = %s AND turno = %s",
                (professor_id, escola_id, turno),
            ).fetchone()
            if not professor:
                raise HorarioTemporarioValidationError("Professor nao encontrado.")

        if disciplina_id:
            disciplina = conn.execute(
                "SELECT id FROM disciplinas WHERE id = %s AND escola_id = %s AND turno = %s",
                (disciplina_id, escola_id, turno),
            ).fetchone()
            if not disciplina:
                raise HorarioTemporarioValidationError("Disciplina nao encontrada.")

        conflito_turma = conn.execute(
            """SELECT id
               FROM horarios_temporarios
               WHERE escola_id = %s
                 AND turno = %s
                 AND turma_id = %s
                 AND dia = %s
                 AND periodo = %s
                 AND data_inicio <= %s
                 AND data_fim >= %s
               LIMIT 1""",
            (escola_id, turno, turma_id, dia, periodo, data_fim, data_inicio),
        ).fetchone()
        if conflito_turma:
            raise HorarioTemporarioValidationError("Ja existe um horario temporario para esta turma nesse periodo.")

        if professor_id:
            conflito_oficial = conn.execute(
                """SELECT id
                   FROM aulas
                   WHERE escola_id = %s
                     AND turno = %s
                     AND professor_id = %s
                     AND dia = %s
                     AND periodo = %s
                     AND turma_id <> %s
                   LIMIT 1""",
                (escola_id, turno, professor_id, dia, periodo, turma_id),
            ).fetchone()
            if conflito_oficial:
                raise HorarioTemporarioValidationError("Este professor ja possui aula oficial nesse periodo.")

            conflito_professor = conn.execute(
                """SELECT id
                   FROM horarios_temporarios
                   WHERE escola_id = %s
                     AND turno = %s
                     AND professor_id = %s
                     AND dia = %s
                     AND periodo = %s
                     AND data_inicio <= %s
                     AND data_fim >= %s
                   LIMIT 1""",
                (escola_id, turno, professor_id, dia, periodo, data_fim, data_inicio),
            ).fetchone()
            if conflito_professor:
                raise HorarioTemporarioValidationError("Este professor ja possui horario temporario nesse periodo.")

        cursor = conn.execute(
            """INSERT INTO horarios_temporarios (
                   escola_id, turno, turma_id, data_inicio, data_fim, dia, periodo,
                   titulo, professor_id, disciplina_id, observacao
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                escola_id,
                turno,
                turma_id,
                data_inicio,
                data_fim,
                dia,
                periodo,
                titulo,
                professor_id,
                disciplina_id,
                observacao,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def criar_horarios_temporarios_lote(
    escola_id,
    turno,
    data_inicio,
    data_fim,
    dia,
    titulo,
    aulas,
    observacao=None,
    substituir=True,
):
    turno = normalizar_turno(turno)
    data_inicio = _parse_date(data_inicio, "Data inicial")
    data_fim = _parse_date(data_fim or data_inicio, "Data final")

    if data_fim < data_inicio:
        raise HorarioTemporarioValidationError("A data final nao pode ser anterior a data inicial.")
    if dia not in DIAS:
        raise HorarioTemporarioValidationError("Dia invalido.")

    titulo = (titulo or "").strip()
    observacao = (observacao or "").strip() or None
    if not titulo:
        raise HorarioTemporarioValidationError("Informe um titulo para o horario temporario.")

    aulas_dia = [
        aula for aula in aulas
        if aula.get("dia") == dia and aula.get("turma_id") and aula.get("periodo")
    ]
    if not aulas_dia:
        raise HorarioTemporarioValidationError("Nenhuma aula foi gerada para este dia.")

    turma_ids = sorted({int(aula["turma_id"]) for aula in aulas_dia})
    professores_por_slot = {}
    turmas_por_slot = {}
    for aula in aulas_dia:
        periodo = int(aula["periodo"])
        professor_id = int(aula["professor_id"]) if aula.get("professor_id") else None
        turma_id = int(aula["turma_id"])
        if periodo not in PERIODOS:
            raise HorarioTemporarioValidationError("Periodo invalido.")

        if professor_id:
            professor_slot = (professor_id, periodo)
            if professor_slot in professores_por_slot:
                raise HorarioTemporarioValidationError("A grade alternativa gerada deixou um professor em conflito.")
            professores_por_slot[professor_slot] = True

        turma_slot = (turma_id, periodo)
        if turma_slot in turmas_por_slot:
            raise HorarioTemporarioValidationError("A grade alternativa gerada deixou uma turma em conflito.")
        turmas_por_slot[turma_slot] = True

    conn = get_connection()
    try:
        placeholders = ", ".join(["%s"] * len(turma_ids))
        turmas = conn.execute(
            f"""SELECT id, COALESCE(aulas_por_dia, 5) AS aulas_por_dia
                FROM turmas
                WHERE escola_id = %s
                  AND turno = %s
                  AND id IN ({placeholders})""",
            tuple([escola_id, turno] + turma_ids),
        ).fetchall()
        turmas_por_id = {int(turma["id"]): turma for turma in turmas}
        if len(turmas_por_id) != len(turma_ids):
            raise HorarioTemporarioValidationError("Uma ou mais turmas nao foram encontradas.")

        for aula in aulas_dia:
            turma = turmas_por_id[int(aula["turma_id"])]
            if int(aula["periodo"]) > int(turma.get("aulas_por_dia") or 5):
                raise HorarioTemporarioValidationError("Periodo invalido para uma das turmas.")

        if substituir:
            for aula in aulas_dia:
                conn.execute(
                    """DELETE FROM horarios_temporarios
                       WHERE escola_id = %s
                         AND turno = %s
                         AND dia = %s
                         AND turma_id = %s
                         AND periodo = %s
                         AND data_inicio <= %s
                         AND data_fim >= %s""",
                    (
                        escola_id,
                        turno,
                        dia,
                        int(aula["turma_id"]),
                        int(aula["periodo"]),
                        data_fim,
                        data_inicio,
                    ),
                )

        if not substituir:
            conflito_turma = conn.execute(
                f"""SELECT id, professor_id, periodo
                    FROM horarios_temporarios
                    WHERE escola_id = %s
                      AND turno = %s
                      AND dia = %s
                      AND turma_id IN ({placeholders})
                      AND data_inicio <= %s
                      AND data_fim >= %s
                    LIMIT 1""",
                tuple([escola_id, turno, dia] + turma_ids + [data_fim, data_inicio]),
            ).fetchone()
            if conflito_turma:
                raise HorarioTemporarioValidationError("Ja existe horario temporario para uma turma nesse periodo.")

            professor_ids = sorted({int(aula["professor_id"]) for aula in aulas_dia if aula.get("professor_id")})
            if professor_ids:
                professor_placeholders = ", ".join(["%s"] * len(professor_ids))
                horarios_professor = conn.execute(
                    f"""SELECT id, professor_id, periodo
                        FROM horarios_temporarios
                        WHERE escola_id = %s
                          AND turno = %s
                          AND dia = %s
                          AND professor_id IN ({professor_placeholders})
                          AND data_inicio <= %s
                          AND data_fim >= %s""",
                    tuple([escola_id, turno, dia] + professor_ids + [data_fim, data_inicio]),
                ).fetchall()
                for horario in horarios_professor:
                    professor_slot = (int(horario["professor_id"]), int(horario["periodo"]))
                    if professor_slot in professores_por_slot:
                        raise HorarioTemporarioValidationError("Um professor ja possui horario temporario nesse periodo.")

        for aula in aulas_dia:
            conn.execute(
                """INSERT INTO horarios_temporarios (
                       escola_id, turno, turma_id, data_inicio, data_fim, dia, periodo,
                       titulo, professor_id, disciplina_id, observacao
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    escola_id,
                    turno,
                    int(aula["turma_id"]),
                    data_inicio,
                    data_fim,
                    dia,
                    int(aula["periodo"]),
                    titulo,
                    int(aula["professor_id"]) if aula.get("professor_id") else None,
                    int(aula["disciplina_id"]) if aula.get("disciplina_id") else None,
                    observacao,
                ),
            )
        conn.commit()
        return len(aulas_dia)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_horario_temporario(horario_id, escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM horarios_temporarios WHERE id = %s AND escola_id = %s AND turno = %s",
            (horario_id, escola_id, turno),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_horarios_temporarios_grupo(
    escola_id,
    turno,
    titulo,
    data_inicio,
    data_fim,
    dia,
    observacao=None,
):
    turno = normalizar_turno(turno)
    data_inicio = _parse_date(data_inicio, "Data inicial")
    data_fim = _parse_date(data_fim or data_inicio, "Data final")
    titulo = (titulo or "").strip()
    observacao = (observacao or "").strip() or None

    conn = get_connection()
    try:
        cursor = conn.execute(
            """DELETE FROM horarios_temporarios
               WHERE escola_id = %s
                 AND turno = %s
                 AND titulo = %s
                 AND data_inicio = %s
                 AND data_fim = %s
                 AND dia = %s
                 AND (
                     (observacao IS NULL AND %s IS NULL)
                     OR observacao = %s
                 )""",
            (escola_id, turno, titulo, data_inicio, data_fim, dia, observacao, observacao),
        )
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
