CREATE TABLE IF NOT EXISTS escolas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL UNIQUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS disciplinas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    nome VARCHAR(255) NOT NULL,
    cor VARCHAR(20) NOT NULL DEFAULT '#22c55e',
    CONSTRAINT fk_disciplinas_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS professores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    nome VARCHAR(255) NOT NULL,
    disciplina_id INT NOT NULL,
    max_aulas_semana INT NOT NULL DEFAULT 10,
    dias_disponiveis TEXT NOT NULL,
    CONSTRAINT fk_professores_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
    CONSTRAINT fk_professores_disciplina
        FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS turmas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    nome VARCHAR(255) NOT NULL,
    CONSTRAINT fk_turmas_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aulas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turma_id INT NOT NULL,
    professor_id INT NOT NULL,
    disciplina_id INT NOT NULL,
    dia VARCHAR(20) NOT NULL,
    periodo INT NOT NULL,
    UNIQUE KEY uq_aulas_turma_slot (turma_id, dia, periodo),
    UNIQUE KEY uq_aulas_professor_slot (professor_id, dia, periodo),
    CONSTRAINT fk_aulas_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
    CONSTRAINT fk_aulas_turma
        FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
    CONSTRAINT fk_aulas_professor
        FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
    CONSTRAINT fk_aulas_disciplina
        FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
