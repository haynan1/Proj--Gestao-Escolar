from database.connection import get_connection


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS escolas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escola_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            cor TEXT NOT NULL DEFAULT '#22c55e',
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS professores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escola_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            disciplina_id INTEGER NOT NULL,
            max_aulas_semana INTEGER NOT NULL DEFAULT 10,
            dias_disponiveis TEXT NOT NULL DEFAULT 'Segunda,Terça,Quarta,Quinta,Sexta',
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
        );

        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escola_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS aulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escola_id INTEGER NOT NULL,
            turma_id INTEGER NOT NULL,
            professor_id INTEGER NOT NULL,
            disciplina_id INTEGER NOT NULL,
            dia TEXT NOT NULL,
            periodo INTEGER NOT NULL,
            FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
            FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()
