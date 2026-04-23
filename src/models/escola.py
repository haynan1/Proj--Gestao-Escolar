from access_control import user_has_permission
from database.connection import get_connection
from models.user_link import usuario_tem_vinculo


def _serialize_escola(row):
    item = dict(row)
    criado_em = item.get('criado_em')
    if hasattr(criado_em, 'strftime'):
        item['criado_em_formatado'] = criado_em.strftime('%Y-%m-%d')
    else:
        item['criado_em_formatado'] = str(criado_em)[:10] if criado_em else None
    return item


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


def listar_escolas_para_usuario(user: dict):
    conn = get_connection()
    try:
        if user_has_permission(user, 'admin_access'):
            escolas = conn.execute(
                """SELECT e.*,
                          dono.nome AS owner_nome
                   FROM escolas e
                   LEFT JOIN usuarios dono ON dono.id = e.user_id
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
    return usuario_tem_vinculo(user['id'], escola['id'])


def deletar_escola(escola_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM escolas WHERE id = %s", (escola_id,))
        conn.commit()
    finally:
        conn.close()


def listar_escolas():
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT e.*, dono.nome AS owner_nome
               FROM escolas e
               LEFT JOIN usuarios dono ON dono.id = e.user_id
               ORDER BY e.nome"""
        ).fetchall()
        return [_serialize_escola(row) for row in rows]
    finally:
        conn.close()
