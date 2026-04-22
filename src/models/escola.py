from database.connection import get_connection


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
        conn.execute(
            "INSERT INTO escolas (user_id, nome) VALUES (%s, %s)",
            (user_id, nome),
        )
        conn.commit()
        return True, "Escola criada com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def listar_escolas(user_id):
    conn = get_connection()
    escolas = conn.execute(
        "SELECT * FROM escolas WHERE user_id = %s ORDER BY nome",
        (user_id,),
    ).fetchall()
    conn.close()
    return [_serialize_escola(e) for e in escolas]


def buscar_escola(escola_id, user_id=None):
    conn = get_connection()
    if user_id is None:
        escola = conn.execute("SELECT * FROM escolas WHERE id = %s", (escola_id,)).fetchone()
    else:
        escola = conn.execute(
            "SELECT * FROM escolas WHERE id = %s AND user_id = %s",
            (escola_id, user_id),
        ).fetchone()
    conn.close()
    return _serialize_escola(escola) if escola else None


def deletar_escola(escola_id, user_id=None):
    conn = get_connection()
    if user_id is None:
        conn.execute("DELETE FROM escolas WHERE id = %s", (escola_id,))
    else:
        conn.execute(
            "DELETE FROM escolas WHERE id = %s AND user_id = %s",
            (escola_id, user_id),
        )
    conn.commit()
    conn.close()
