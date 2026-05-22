from database.connection import get_connection
from models.turno import normalizar_turno


def salvar_sugestao(escola_id, aulas, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM grade_sugestao WHERE escola_id = %s AND turno = %s",
            (escola_id, turno),
        )
        for a in aulas:
            conn.execute(
                """INSERT INTO grade_sugestao
                   (escola_id, turno, turma_id, professor_id, disciplina_id, dia, periodo, tem_conflito)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    escola_id, turno,
                    a['turma_id'], a['professor_id'], a['disciplina_id'],
                    a['dia'], a['periodo'],
                    int(bool(a.get('tem_conflito', False))),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_sugestao(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    rows = conn.execute(
        """SELECT gs.*, t.nome AS turma_nome,
                  p.nome AS professor_nome, p.cor AS professor_cor, p.dias_disponiveis,
                  d.nome AS disciplina_nome, d.cor AS disciplina_cor
           FROM grade_sugestao gs
           JOIN turmas t ON gs.turma_id = t.id
           JOIN professores p ON gs.professor_id = p.id
           JOIN disciplinas d ON gs.disciplina_id = d.id
           WHERE gs.escola_id = %s AND gs.turno = %s
           ORDER BY gs.turma_id, gs.dia, gs.periodo""",
        (escola_id, turno),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def limpar_sugestao(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM grade_sugestao WHERE escola_id = %s AND turno = %s",
            (escola_id, turno),
        )
        conn.commit()
    finally:
        conn.close()


def tem_sugestao(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM grade_sugestao WHERE escola_id = %s AND turno = %s",
        (escola_id, turno),
    ).fetchone()
    conn.close()
    return bool(row and row['total'])
