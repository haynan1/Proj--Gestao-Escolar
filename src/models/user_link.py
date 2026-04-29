from database.connection import get_connection


def listar_vinculos():
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT ue.id,
                      ue.usuario_id,
                      ue.escola_id,
                      ue.criado_em,
                      u.nome AS usuario_nome,
                      u.email AS usuario_email,
                      u.role AS usuario_role,
                      e.nome AS escola_nome
               FROM usuarios_escolas ue
               JOIN usuarios u ON u.id = ue.usuario_id
               JOIN escolas e ON e.id = ue.escola_id
               WHERE e.oculta = 0
               ORDER BY e.nome, u.nome"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def listar_vinculos_por_usuario(usuario_id: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT ue.id,
                      ue.usuario_id,
                      ue.escola_id,
                      ue.criado_em,
                      e.nome AS escola_nome
               FROM usuarios_escolas ue
               JOIN escolas e ON e.id = ue.escola_id
               WHERE ue.usuario_id = %s
                 AND e.oculta = 0
               ORDER BY e.nome""",
            (usuario_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def criar_vinculo_usuario_escola(usuario_id: int, escola_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO usuarios_escolas (usuario_id, escola_id) VALUES (%s, %s)",
            (usuario_id, escola_id),
        )
        conn.commit()
        return True, 'Vinculo criado com sucesso.'
    except Exception as exc:
        conn.rollback()
        mensagem = str(exc)
        if 'Duplicate entry' in mensagem:
            return False, 'Este usuario ja esta vinculado a esta escola.'
        return False, mensagem
    finally:
        conn.close()


def deletar_vinculo(vinculo_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM usuarios_escolas WHERE id = %s",
            (vinculo_id,),
        )
        conn.commit()
    finally:
        conn.close()


def usuario_tem_vinculo(usuario_id: int, escola_id: int) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT id
               FROM usuarios_escolas
               WHERE usuario_id = %s AND escola_id = %s""",
            (usuario_id, escola_id),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()
