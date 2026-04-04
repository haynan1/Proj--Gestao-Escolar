from database.connection import get_connection


def _serialize_escola(row):
    item = dict(row)
    criado_em = item.get('criado_em')
    if hasattr(criado_em, 'strftime'):
        item['criado_em_formatado'] = criado_em.strftime('%Y-%m-%d')
    else:
        item['criado_em_formatado'] = str(criado_em)[:10] if criado_em else None
    return item


def criar_escola(nome):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO escolas (nome) VALUES (%s)", (nome,))
        conn.commit()
        return True, "Escola criada com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def listar_escolas():
    conn = get_connection()
    escolas = conn.execute("SELECT * FROM escolas ORDER BY nome").fetchall()
    conn.close()
    return [_serialize_escola(e) for e in escolas]


def buscar_escola(escola_id):
    conn = get_connection()
    escola = conn.execute("SELECT * FROM escolas WHERE id = %s", (escola_id,)).fetchone()
    conn.close()
    return _serialize_escola(escola) if escola else None


def deletar_escola(escola_id):
    conn = get_connection()
    conn.execute("DELETE FROM escolas WHERE id = %s", (escola_id,))
    conn.commit()
    conn.close()
