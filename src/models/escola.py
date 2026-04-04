from database.connection import get_connection


def criar_escola(nome):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO escolas (nome) VALUES (?)", (nome,))
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
    return [dict(e) for e in escolas]


def buscar_escola(escola_id):
    conn = get_connection()
    escola = conn.execute("SELECT * FROM escolas WHERE id = ?", (escola_id,)).fetchone()
    conn.close()
    return dict(escola) if escola else None


def deletar_escola(escola_id):
    conn = get_connection()
    conn.execute("DELETE FROM escolas WHERE id = ?", (escola_id,))
    conn.commit()
    conn.close()
