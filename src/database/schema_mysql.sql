CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'funcionario',
    email_verificado TINYINT(1) NOT NULL DEFAULT 0,
    email_verificado_em TIMESTAMP NULL DEFAULT NULL,
    token_version INT NOT NULL DEFAULT 0,
    tentativas_login_falhas INT NOT NULL DEFAULT 0,
    bloqueado_ate TIMESTAMP NULL DEFAULT NULL,
    ultimo_login_em TIMESTAMP NULL DEFAULT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS escolas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    nome VARCHAR(255) NOT NULL,
    oculta TINYINT(1) NOT NULL DEFAULT 0,
    backup_de_escola_id INT NULL,
    horarios_travados_turnos VARCHAR(100) NOT NULL DEFAULT '',
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_escolas_oculta (oculta),
    KEY idx_escolas_backup_de (backup_de_escola_id),
    UNIQUE KEY uq_escolas_usuario_nome (user_id, nome),
    CONSTRAINT fk_escolas_usuario
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS usuarios_escolas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    escola_id INT NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usuarios_escolas (usuario_id, escola_id),
    CONSTRAINT fk_usuarios_escolas_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_usuarios_escolas_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS disciplinas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
    nome VARCHAR(255) NOT NULL,
    cor VARCHAR(20) NULL DEFAULT NULL,
    CONSTRAINT fk_disciplinas_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS professores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
    nome VARCHAR(255) NOT NULL,
    cor VARCHAR(20) NULL DEFAULT NULL,
    disciplina_id INT NOT NULL,
    max_aulas_semana INT NOT NULL DEFAULT 10,
    dias_disponiveis TEXT NOT NULL,
    CONSTRAINT fk_professores_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
    CONSTRAINT fk_professores_disciplina
        FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS professores_disciplinas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    professor_id INT NOT NULL,
    disciplina_id INT NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_professores_disciplinas (professor_id, disciplina_id),
    CONSTRAINT fk_professores_disciplinas_professor
        FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
    CONSTRAINT fk_professores_disciplinas_disciplina
        FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS turmas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
    nome VARCHAR(255) NOT NULL,
    aulas_por_dia INT NOT NULL DEFAULT 5,
    CONSTRAINT fk_turmas_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS professores_turmas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    professor_id INT NOT NULL,
    turma_id INT NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_professores_turmas (professor_id, turma_id),
    CONSTRAINT fk_professores_turmas_professor
        FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE CASCADE,
    CONSTRAINT fk_professores_turmas_turma
        FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aulas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
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

CREATE TABLE IF NOT EXISTS horarios_temporarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
    turma_id INT NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE NOT NULL,
    dia VARCHAR(20) NOT NULL,
    periodo INT NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    professor_id INT NULL,
    disciplina_id INT NULL,
    observacao TEXT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_horarios_temp_escola_turno (escola_id, turno),
    KEY idx_horarios_temp_turma_datas (turma_id, data_inicio, data_fim),
    CONSTRAINT fk_horarios_temp_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
    CONSTRAINT fk_horarios_temp_turma
        FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
    CONSTRAINT fk_horarios_temp_professor
        FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE SET NULL,
    CONSTRAINT fk_horarios_temp_disciplina
        FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS relatorios_professores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
    professor_id INT NULL,
    professor_nome_snapshot VARCHAR(255) NOT NULL DEFAULT '',
    professor_cor_snapshot VARCHAR(20) NULL DEFAULT NULL,
    data_ocorrencia DATE NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    descricao TEXT NOT NULL,
    criado_por_usuario_id INT NULL,
    excluido_em TIMESTAMP NULL DEFAULT NULL,
    excluido_por_usuario_id INT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_relatorios_prof_escola_turno_data (escola_id, turno, data_ocorrencia),
    KEY idx_relatorios_prof_escola_turno_excluido (escola_id, turno, excluido_em),
    KEY idx_relatorios_prof_professor_data (professor_id, data_ocorrencia),
    CONSTRAINT fk_relatorios_prof_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
    CONSTRAINT fk_relatorios_prof_professor
        FOREIGN KEY (professor_id) REFERENCES professores(id) ON DELETE SET NULL,
    CONSTRAINT fk_relatorios_prof_criado_por
        FOREIGN KEY (criado_por_usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    CONSTRAINT fk_relatorios_prof_excluido_por
        FOREIGN KEY (excluido_por_usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prontuarios_alunos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escola_id INT NOT NULL,
    turno VARCHAR(20) NOT NULL DEFAULT 'matutino',
    aluno_nome VARCHAR(255) NOT NULL,
    turma_id INT NOT NULL,
    professor_marcado_id INT NULL,
    prioridade VARCHAR(20) NOT NULL DEFAULT 'media',
    status VARCHAR(30) NOT NULL DEFAULT 'aberto',
    observacao TEXT NOT NULL,
    feedback TEXT NULL,
    data_registro DATE NOT NULL,
    criado_por_usuario_id INT NULL,
    feedback_por_usuario_id INT NULL,
    feedback_em TIMESTAMP NULL DEFAULT NULL,
    excluido_em TIMESTAMP NULL DEFAULT NULL,
    excluido_por_usuario_id INT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_prontuarios_escola_turno_status (escola_id, turno, status),
    KEY idx_prontuarios_turma_data (turma_id, data_registro),
    KEY idx_prontuarios_professor_status (professor_marcado_id, status),
    CONSTRAINT fk_prontuarios_escola
        FOREIGN KEY (escola_id) REFERENCES escolas(id) ON DELETE CASCADE,
    CONSTRAINT fk_prontuarios_turma
        FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
    CONSTRAINT fk_prontuarios_professor
        FOREIGN KEY (professor_marcado_id) REFERENCES professores(id) ON DELETE SET NULL,
    CONSTRAINT fk_prontuarios_criado_por
        FOREIGN KEY (criado_por_usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    CONSTRAINT fk_prontuarios_feedback_por
        FOREIGN KEY (feedback_por_usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    CONSTRAINT fk_prontuarios_excluido_por
        FOREIGN KEY (excluido_por_usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
