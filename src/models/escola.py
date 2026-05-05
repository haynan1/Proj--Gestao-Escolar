from datetime import datetime
import re

from access_control import user_has_permission
from database.connection import get_connection
from models.turno import normalizar_turno
from models.user_link import usuario_tem_vinculo

BACKUP_NAME_RE = re.compile(r'\s+\(backup \d{4}-\d{2}-\d{2} \d{6}\)(?: \d+)?$')


def _serialize_escola(row):
    item = dict(row)
    criado_em = item.get('criado_em')
    if hasattr(criado_em, 'strftime'):
        item['criado_em_formatado'] = criado_em.strftime('%Y-%m-%d')
    else:
        item['criado_em_formatado'] = str(criado_em)[:10] if criado_em else None
    return item


def _parse_turnos_travados(value):
    return {
        normalizar_turno(turno)
        for turno in str(value or '').split(',')
        if str(turno or '').strip()
    }


def horario_turno_travado(escola, turno):
    if not escola:
        return False
    turno = normalizar_turno(turno)
    return turno in _parse_turnos_travados(escola.get('horarios_travados_turnos'))


def definir_horario_turno_travado(escola_id, turno, travado):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        escola = conn.execute(
            "SELECT horarios_travados_turnos FROM escolas WHERE id = %s",
            (escola_id,),
        ).fetchone()
        if not escola:
            return False

        turnos = _parse_turnos_travados(escola.get('horarios_travados_turnos'))
        if travado:
            turnos.add(turno)
        else:
            turnos.discard(turno)

        conn.execute(
            "UPDATE escolas SET horarios_travados_turnos = %s WHERE id = %s",
            (','.join(sorted(turnos)), escola_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def criar_escola(user_id, nome):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO escolas (user_id, nome) VALUES (%s, %s)",
            (user_id, nome),
        )
        escola_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO usuarios_escolas (usuario_id, escola_id)
               VALUES (%s, %s)""",
            (user_id, escola_id),
        )
        conn.commit()
        return True, "Escola criada com sucesso."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def atualizar_nome_escola(escola_id, nome):
    nome = (nome or '').strip()
    if not nome:
        return False, 'O nome da escola e obrigatorio.'

    conn = get_connection()
    try:
        escola = conn.execute(
            "SELECT id, user_id, nome FROM escolas WHERE id = %s AND oculta = 0",
            (escola_id,),
        ).fetchone()
        if not escola:
            return False, 'Escola nao encontrada.'

        if escola['nome'] == nome:
            return True, 'Nome da escola mantido.'

        if not _nome_disponivel_para_escola(conn, escola.get('user_id'), nome, escola_id):
            return False, 'Ja existe uma escola com esse nome para este responsavel.'

        conn.execute(
            "UPDATE escolas SET nome = %s WHERE id = %s AND oculta = 0",
            (nome, escola_id),
        )
        conn.commit()
        return True, 'Nome da escola atualizado com sucesso.'
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def listar_escolas_para_usuario(user: dict):
    conn = get_connection()
    try:
        if user_has_permission(user, 'admin_access'):
            escolas = conn.execute(
                """SELECT e.*,
                          dono.nome AS owner_nome
                   FROM escolas e
                   LEFT JOIN usuarios dono ON dono.id = e.user_id
                   WHERE e.oculta = 0
                   ORDER BY e.nome"""
            ).fetchall()
        else:
            escolas = conn.execute(
                """SELECT e.*,
                          dono.nome AS owner_nome
                   FROM escolas e
                   LEFT JOIN usuarios dono ON dono.id = e.user_id
                   JOIN usuarios_escolas ue
                     ON ue.escola_id = e.id
                  WHERE ue.usuario_id = %s
                    AND e.oculta = 0
                   ORDER BY e.nome""",
                (user['id'],),
            ).fetchall()
        return [_serialize_escola(e) for e in escolas]
    finally:
        conn.close()


def buscar_escola(escola_id, user=None):
    conn = get_connection()
    try:
        escola = conn.execute(
            """SELECT e.*,
                      dono.nome AS owner_nome
               FROM escolas e
               LEFT JOIN usuarios dono ON dono.id = e.user_id
               WHERE e.id = %s""",
            (escola_id,),
        ).fetchone()
        escola = _serialize_escola(escola) if escola else None
        if not escola:
            return None
        if escola.get('oculta') and not user_has_permission(user, 'admin_access'):
            return None
        if not user or usuario_pode_acessar_escola(user, escola):
            return escola
        return None
    finally:
        conn.close()


def usuario_pode_acessar_escola(user: dict | None, escola: dict | None) -> bool:
    if not user or not escola:
        return False
    if user_has_permission(user, 'admin_access'):
        return True
    if escola.get('oculta'):
        return False
    return usuario_tem_vinculo(user['id'], escola['id'])


def _deletar_dados_escola(conn, escola_id):
    conn.execute("DELETE FROM horarios_temporarios WHERE escola_id = %s", (escola_id,))
    conn.execute("DELETE FROM aulas WHERE escola_id = %s", (escola_id,))
    conn.execute(
        """DELETE pc
           FROM professores_cargas pc
           JOIN professores p ON p.id = pc.professor_id
           WHERE p.escola_id = %s""",
        (escola_id,),
    )
    conn.execute(
        """DELETE pt
           FROM professores_turmas pt
           JOIN professores p ON p.id = pt.professor_id
           WHERE p.escola_id = %s""",
        (escola_id,),
    )
    conn.execute(
        """DELETE pd
           FROM professores_disciplinas pd
           JOIN professores p ON p.id = pd.professor_id
           WHERE p.escola_id = %s""",
        (escola_id,),
    )
    conn.execute("DELETE FROM professores WHERE escola_id = %s", (escola_id,))
    conn.execute("DELETE FROM turmas WHERE escola_id = %s", (escola_id,))
    conn.execute("DELETE FROM disciplinas WHERE escola_id = %s", (escola_id,))


def deletar_escola(escola_id):
    conn = get_connection()
    try:
        _deletar_dados_escola(conn, escola_id)
        conn.execute("DELETE FROM escolas WHERE id = %s", (escola_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _gerar_nome_backup(conn, escola):
    base = f"{escola['nome']} (backup {datetime.now().strftime('%Y-%m-%d %H%M%S')})"
    nome = base
    for indice in range(2, 30):
        existente = conn.execute(
            """SELECT id
               FROM escolas
               WHERE user_id <=> %s
                 AND nome = %s""",
            (escola.get('user_id'), nome),
        ).fetchone()
        if not existente:
            return nome
        nome = f"{base} {indice}"
    return f"{base} {datetime.now().microsecond}"


def _nome_disponivel_para_escola(conn, user_id, nome, escola_id_ignorado=None):
    params = [user_id, nome]
    filtro_ignorado = ''
    if escola_id_ignorado:
        filtro_ignorado = ' AND id <> %s'
        params.append(escola_id_ignorado)

    existente = conn.execute(
        f"""SELECT id
            FROM escolas
            WHERE user_id <=> %s
              AND nome = %s
              {filtro_ignorado}
            LIMIT 1""",
        tuple(params),
    ).fetchone()
    return existente is None


def _gerar_nome_restaurado(conn, backup):
    nome_limpo = BACKUP_NAME_RE.sub('', backup['nome']).strip()
    if nome_limpo and _nome_disponivel_para_escola(conn, backup.get('user_id'), nome_limpo, backup['id']):
        return nome_limpo

    if _nome_disponivel_para_escola(conn, backup.get('user_id'), backup['nome'], backup['id']):
        return backup['nome']

    base = nome_limpo or backup['nome']
    timestamp = datetime.now().strftime('%Y-%m-%d %H%M%S')
    nome = f"{base} (restaurada {timestamp})"
    for indice in range(2, 30):
        if _nome_disponivel_para_escola(conn, backup.get('user_id'), nome, backup['id']):
            return nome
        nome = f"{base} (restaurada {timestamp}) {indice}"
    return f"{base} (restaurada {timestamp}) {datetime.now().microsecond}"


def duplicar_escola_oculta(escola_id):
    conn = get_connection()
    try:
        escola = conn.execute(
            "SELECT * FROM escolas WHERE id = %s AND oculta = 0",
            (escola_id,),
        ).fetchone()
        if not escola:
            return False, 'Escola nao encontrada para backup.', None

        nome_backup = _gerar_nome_backup(conn, escola)
        cursor = conn.execute(
            """INSERT INTO escolas (
                   user_id,
                   nome,
                   oculta,
                   backup_de_escola_id,
                   horarios_travados_turnos
               ) VALUES (%s, %s, 1, %s, %s)""",
            (
                escola.get('user_id'),
                nome_backup,
                escola['id'],
                escola.get('horarios_travados_turnos') or '',
            ),
        )
        backup_id = cursor.lastrowid

        disciplina_map = {}
        disciplinas = conn.execute(
            "SELECT * FROM disciplinas WHERE escola_id = %s ORDER BY id",
            (escola_id,),
        ).fetchall()
        for disciplina in disciplinas:
            cursor = conn.execute(
                "INSERT INTO disciplinas (escola_id, nome, cor) VALUES (%s, %s, %s)",
                (backup_id, disciplina['nome'], disciplina['cor']),
            )
            disciplina_map[disciplina['id']] = cursor.lastrowid

        turma_map = {}
        turmas = conn.execute(
            "SELECT * FROM turmas WHERE escola_id = %s ORDER BY id",
            (escola_id,),
        ).fetchall()
        for turma in turmas:
            cursor = conn.execute(
                "INSERT INTO turmas (escola_id, nome, aulas_por_dia) VALUES (%s, %s, %s)",
                (backup_id, turma['nome'], turma.get('aulas_por_dia') or 5),
            )
            turma_map[turma['id']] = cursor.lastrowid

        professor_map = {}
        professores = conn.execute(
            "SELECT * FROM professores WHERE escola_id = %s ORDER BY id",
            (escola_id,),
        ).fetchall()
        for professor in professores:
            disciplina_id = disciplina_map.get(professor['disciplina_id'])
            if not disciplina_id:
                continue
            cursor = conn.execute(
                """INSERT INTO professores (
                       escola_id,
                       nome,
                       cor,
                       disciplina_id,
                       max_aulas_semana,
                       dias_disponiveis
                   ) VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    backup_id,
                    professor['nome'],
                    professor.get('cor') or '#3b82f6',
                    disciplina_id,
                    professor.get('max_aulas_semana') or 10,
                    professor.get('dias_disponiveis') or '',
                ),
            )
            professor_map[professor['id']] = cursor.lastrowid

        for row in conn.execute(
            """SELECT pd.professor_id, pd.disciplina_id
               FROM professores_disciplinas pd
               JOIN professores p ON p.id = pd.professor_id
               WHERE p.escola_id = %s""",
            (escola_id,),
        ).fetchall():
            professor_id = professor_map.get(row['professor_id'])
            disciplina_id = disciplina_map.get(row['disciplina_id'])
            if professor_id and disciplina_id:
                conn.execute(
                    """INSERT IGNORE INTO professores_disciplinas (professor_id, disciplina_id)
                       VALUES (%s, %s)""",
                    (professor_id, disciplina_id),
                )

        for row in conn.execute(
            """SELECT pt.professor_id, pt.turma_id
               FROM professores_turmas pt
               JOIN professores p ON p.id = pt.professor_id
               WHERE p.escola_id = %s""",
            (escola_id,),
        ).fetchall():
            professor_id = professor_map.get(row['professor_id'])
            turma_id = turma_map.get(row['turma_id'])
            if professor_id and turma_id:
                conn.execute(
                    """INSERT IGNORE INTO professores_turmas (professor_id, turma_id)
                       VALUES (%s, %s)""",
                    (professor_id, turma_id),
                )

        for row in conn.execute(
            """SELECT pc.professor_id,
                      pc.turma_id,
                      pc.disciplina_id,
                      pc.aulas_semana
               FROM professores_cargas pc
               JOIN professores p ON p.id = pc.professor_id
               WHERE p.escola_id = %s""",
            (escola_id,),
        ).fetchall():
            professor_id = professor_map.get(row['professor_id'])
            turma_id = turma_map.get(row['turma_id'])
            disciplina_id = disciplina_map.get(row['disciplina_id'])
            if professor_id and turma_id and disciplina_id:
                conn.execute(
                    """INSERT IGNORE INTO professores_cargas (
                           professor_id,
                           turma_id,
                           disciplina_id,
                           aulas_semana
                       ) VALUES (%s, %s, %s, %s)""",
                    (professor_id, turma_id, disciplina_id, row.get('aulas_semana') or 1),
                )

        for aula in conn.execute(
            "SELECT * FROM aulas WHERE escola_id = %s ORDER BY id",
            (escola_id,),
        ).fetchall():
            turma_id = turma_map.get(aula['turma_id'])
            professor_id = professor_map.get(aula['professor_id'])
            disciplina_id = disciplina_map.get(aula['disciplina_id'])
            if turma_id and professor_id and disciplina_id:
                conn.execute(
                    """INSERT INTO aulas (
                           escola_id,
                           turma_id,
                           professor_id,
                           disciplina_id,
                           dia,
                           periodo
                       ) VALUES (%s, %s, %s, %s, %s, %s)""",
                    (backup_id, turma_id, professor_id, disciplina_id, aula['dia'], aula['periodo']),
                )

        conn.commit()
        return True, f'Backup oculto criado com sucesso: {nome_backup}.', backup_id
    except Exception:
        conn.rollback()
        return False, 'Nao foi possivel criar o backup oculto desta escola.', None
    finally:
        conn.close()


def listar_escolas():
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT e.*, dono.nome AS owner_nome
               FROM escolas e
               LEFT JOIN usuarios dono ON dono.id = e.user_id
               WHERE e.oculta = 0
               ORDER BY e.nome"""
        ).fetchall()
        return [_serialize_escola(row) for row in rows]
    finally:
        conn.close()


def listar_backups_ocultos():
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT backup.*,
                      dono.nome AS owner_nome,
                      original.nome AS escola_original_nome,
                      (
                          SELECT COUNT(*)
                          FROM turmas t
                          WHERE t.escola_id = backup.id
                      ) AS total_turmas,
                      (
                          SELECT COUNT(*)
                          FROM professores p
                          WHERE p.escola_id = backup.id
                      ) AS total_professores,
                      (
                          SELECT COUNT(*)
                          FROM aulas a
                          WHERE a.escola_id = backup.id
                      ) AS total_aulas
               FROM escolas backup
               LEFT JOIN usuarios dono ON dono.id = backup.user_id
               LEFT JOIN escolas original ON original.id = backup.backup_de_escola_id
               WHERE backup.oculta = 1
               ORDER BY backup.criado_em DESC, backup.nome"""
        ).fetchall()
        return [_serialize_escola(row) for row in rows]
    finally:
        conn.close()


def restaurar_backup_oculto(escola_id):
    conn = get_connection()
    try:
        backup = conn.execute(
            "SELECT * FROM escolas WHERE id = %s AND oculta = 1",
            (escola_id,),
        ).fetchone()
        if not backup:
            return False, 'Backup oculto nao encontrado.', None

        nome_restaurado = _gerar_nome_restaurado(conn, backup)
        conn.execute(
            """UPDATE escolas
               SET nome = %s,
                   oculta = 0,
                   backup_de_escola_id = NULL
               WHERE id = %s AND oculta = 1""",
            (nome_restaurado, escola_id),
        )
        conn.execute(
            """INSERT IGNORE INTO usuarios_escolas (usuario_id, escola_id)
               SELECT user_id, id
               FROM escolas
               WHERE id = %s
                 AND user_id IS NOT NULL""",
            (escola_id,),
        )
        conn.commit()
        return True, f'Backup restaurado como escola visivel: {nome_restaurado}.', escola_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deletar_backup_oculto(escola_id):
    conn = get_connection()
    try:
        backup = conn.execute(
            "SELECT id FROM escolas WHERE id = %s AND oculta = 1",
            (escola_id,),
        ).fetchone()
        if not backup:
            return False

        _deletar_dados_escola(conn, escola_id)
        cursor = conn.execute(
            "DELETE FROM escolas WHERE id = %s AND oculta = 1",
            (escola_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
