"""Validações de mover_aula — o backend do arrasto de aulas na grade.

Cobre o que pode ser exercitado sem banco: validação de entrada, guarda de escola,
recusa de vagas e a regra de no máximo 2 aulas seguidas da mesma disciplina.
Conflitos de professor e a troca atômica dependem de MySQL e ficam fora daqui.
"""
from unittest.mock import MagicMock

import pytest

from models import aula as A


def cursor_com(row=None, rows=None, rowcount=0):
    c = MagicMock()
    c.fetchone.return_value = row
    c.fetchall.return_value = rows if rows is not None else []
    c.rowcount = rowcount
    c.lastrowid = 1
    return c


def conn_roteirizado(*cursores):
    """Conexão cujo execute() devolve os cursores na ordem em que forem pedidos."""
    conn = MagicMock()
    conn.execute.side_effect = list(cursores)
    return conn


def aula_row(**over):
    base = {
        'id': 1, 'escola_id': 10, 'turma_id': 20, 'professor_id': 30,
        'disciplina_id': 40, 'dia': 'Segunda', 'periodo': 1, 'vaga': 0,
        'aulas_por_dia': 5,
    }
    base.update(over)
    return base


# ─── validação de entrada ───────────────────────────────────────────────────

def test_dia_invalido_recusado_antes_de_abrir_conexao(monkeypatch):
    chamou = []
    monkeypatch.setattr(A, 'get_connection', lambda: chamou.append(1))

    with pytest.raises(A.ScheduleValidationError, match='Dia inválido'):
        A.mover_aula(1, 'Sabado', 1, escola_id=10)

    assert not chamou, 'abriu conexão para um dia que nem existe na grade'


@pytest.mark.parametrize('periodo', [0, -1, 6, 99])
def test_periodo_fora_da_grade_da_turma(monkeypatch, periodo):
    conn = conn_roteirizado(cursor_com(row=aula_row(aulas_por_dia=5)))
    monkeypatch.setattr(A, 'get_connection', lambda: conn)

    with pytest.raises(A.ScheduleValidationError, match='Período inválido'):
        A.mover_aula(1, 'Terça', periodo, escola_id=10)


def test_aula_inexistente(monkeypatch):
    monkeypatch.setattr(A, 'get_connection', lambda: conn_roteirizado(cursor_com(row=None)))

    with pytest.raises(A.ScheduleValidationError, match='não encontrada'):
        A.mover_aula(999, 'Terça', 1, escola_id=10)


def test_vaga_nao_pode_ser_arrastada(monkeypatch):
    monkeypatch.setattr(A, 'get_connection', lambda: conn_roteirizado(cursor_com(row=aula_row(vaga=1))))

    with pytest.raises(A.ScheduleValidationError, match='mover uma vaga'):
        A.mover_aula(1, 'Terça', 1, escola_id=10)


def test_aula_de_outra_escola_e_recusada(monkeypatch):
    monkeypatch.setattr(A, 'get_connection', lambda: conn_roteirizado(cursor_com(row=aula_row(escola_id=99))))

    with pytest.raises(A.ScheduleValidationError, match='não pertence a esta escola'):
        A.mover_aula(1, 'Terça', 1, escola_id=10)


def test_sem_escola_id_a_guarda_de_tenant_nao_roda(monkeypatch):
    """escola_id é opcional na assinatura: quem chama precisa passar (a rota passa)."""
    conn = conn_roteirizado(cursor_com(row=aula_row(escola_id=99, vaga=1)))
    monkeypatch.setattr(A, 'get_connection', lambda: conn)

    # sem escola_id a aula de outra escola passa da guarda de tenant e só é barrada por ser vaga
    with pytest.raises(A.ScheduleValidationError, match='mover uma vaga'):
        A.mover_aula(1, 'Terça', 1)


def test_rollback_e_close_sempre_acontecem(monkeypatch):
    conn = conn_roteirizado(cursor_com(row=aula_row(vaga=1)))
    monkeypatch.setattr(A, 'get_connection', lambda: conn)

    with pytest.raises(A.ScheduleValidationError):
        A.mover_aula(1, 'Terça', 1, escola_id=10)

    conn.rollback.assert_called_once()
    conn.close.assert_called_once()
    conn.commit.assert_not_called()


# ─── máximo de 2 aulas seguidas da mesma disciplina ─────────────────────────

def _seguidas(periodos_existentes, periodo_alvo, ignorar=None):
    rows = [{'id': 100 + i, 'periodo': p} for i, p in enumerate(periodos_existentes)]
    conn = conn_roteirizado(cursor_com(rows=rows))
    A._validar_aulas_seguidas_disciplina(conn, 10, 20, 40, 'Segunda', periodo_alvo,
                                         ignorar_aula_ids=ignorar)


def test_duas_seguidas_sao_permitidas():
    _seguidas([1], 2)  # 1,2 -> ok


def test_tres_seguidas_bloqueadas_no_fim():
    with pytest.raises(A.ScheduleConflictError, match='2 aulas seguidas'):
        _seguidas([1, 2], 3)


def test_tres_seguidas_bloqueadas_no_meio():
    with pytest.raises(A.ScheduleConflictError):
        _seguidas([1, 3], 2)


def test_tres_seguidas_bloqueadas_no_inicio():
    with pytest.raises(A.ScheduleConflictError):
        _seguidas([2, 3], 1)


def test_aulas_espalhadas_nao_bloqueiam():
    _seguidas([1, 3, 5], 7)


def test_aula_ignorada_nao_conta_como_seguida():
    # a própria aula sendo movida não pode contar contra ela mesma
    conn = conn_roteirizado(cursor_com(rows=[{'id': 100, 'periodo': 1}, {'id': 101, 'periodo': 2}]))
    A._validar_aulas_seguidas_disciplina(conn, 10, 20, 40, 'Segunda', 3, ignorar_aula_ids=[101])


def test_periodo_1_nao_estoura_para_periodo_negativo():
    _seguidas([], 1)


# ─── dias disponíveis do professor ──────────────────────────────────────────

@pytest.mark.parametrize('bruto,esperado', [
    (None, []),
    ('', []),
    ('Segunda', ['Segunda']),
    ('Segunda,Terça', ['Segunda', 'Terça']),
    (' Segunda , Terça ', ['Segunda', 'Terça']),
    ('Segunda,,Terça', ['Segunda', 'Terça']),
])
def test_parse_dos_dias_do_professor(bruto, esperado):
    assert A._dias_disponiveis_professor({'dias_disponiveis': bruto}) == esperado


def test_professor_inexistente_nao_bloqueia_por_dia():
    assert A._dias_disponiveis_professor(None) == []


def test_dia_fora_da_disponibilidade_bloqueia():
    conn = conn_roteirizado(cursor_com(row={'dias_disponiveis': 'Segunda,Quarta'}))
    with pytest.raises(A.ScheduleConflictError, match='não está disponível'):
        A._validar_disponibilidade_professor(conn, 10, 30, 'Terça')


def test_dia_dentro_da_disponibilidade_passa():
    conn = conn_roteirizado(cursor_com(row={'dias_disponiveis': 'Segunda,Quarta'}))
    A._validar_disponibilidade_professor(conn, 10, 30, 'Quarta')


def test_sem_dias_cadastrados_nao_restringe():
    # coluna vazia significa "sem restrição" — não pode virar "bloqueia tudo"
    conn = conn_roteirizado(cursor_com(row={'dias_disponiveis': ''}))
    A._validar_disponibilidade_professor(conn, 10, 30, 'Sexta')


# ─── regras do professor aplicadas à edição manual ──────────────────────────

from models import regra_professor as R  # noqa: E402


def _regra(tipo, parametros, obrigatoria=True, escopo=None):
    return {'tipo': tipo, 'parametros': parametros, 'obrigatoria': obrigatoria,
            'escopo_disciplina_id': escopo, 'escopo_disciplina_nome': None}


def _com_regras(monkeypatch, regras):
    monkeypatch.setattr(A._regras, 'carregar_regras_professor', lambda conn, pid: regras)


def test_slot_proibido_por_regra_bloqueia_o_arrasto(monkeypatch):
    _com_regras(monkeypatch, [_regra(R.PERIODO_PROIBIDO, {'periodos': [5]})])

    with pytest.raises(A.ScheduleConflictError, match='regra do professor'):
        A._validar_regras_professor(MagicMock(), 30, 20, 40, 'Segunda', 5, 5)


def test_mensagem_de_bloqueio_descreve_a_regra(monkeypatch):
    _com_regras(monkeypatch, [_regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']})])

    with pytest.raises(A.ScheduleConflictError, match='Só pode em Segunda'):
        A._validar_regras_professor(MagicMock(), 30, 20, 40, 'Sexta', 1, 5)


def test_slot_permitido_por_regra_passa(monkeypatch):
    _com_regras(monkeypatch, [_regra(R.PERIODO_PROIBIDO, {'periodos': [5]})])

    A._validar_regras_professor(conn_roteirizado(), 30, 20, 40, 'Segunda', 1, 5)


def test_regra_de_preferencia_nao_bloqueia_arrasto(monkeypatch):
    _com_regras(monkeypatch, [_regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}, obrigatoria=False)])

    A._validar_regras_professor(conn_roteirizado(), 30, 20, 40, 'Sexta', 1, 5)


def test_regra_de_outra_disciplina_nao_bloqueia(monkeypatch):
    _com_regras(monkeypatch, [_regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}, escopo=99)])

    A._validar_regras_professor(conn_roteirizado(), 30, 20, 40, 'Sexta', 1, 5)


def test_aula_sem_professor_nao_consulta_regras(monkeypatch):
    chamou = []
    monkeypatch.setattr(A._regras, 'carregar_regras_professor',
                        lambda conn, pid: chamou.append(pid) or [])

    A._validar_regras_professor(MagicMock(), None, 20, 40, 'Segunda', 1, 5)
    assert not chamou


def test_periodos_da_turma_saem_do_aulas_por_dia(monkeypatch):
    # "últimas 1" numa turma de 4 períodos é o período 4, não o 5
    _com_regras(monkeypatch, [_regra(R.SLOT_FIXO, {'dia': 'Terça', 'posicao': 'ultimas', 'quantidade': 1})])

    A._validar_regras_professor(conn_roteirizado(), 30, 20, 40, 'Terça', 4, 4)
    with pytest.raises(A.ScheduleConflictError):
        A._validar_regras_professor(MagicMock(), 30, 20, 40, 'Terça', 5, 4)


# ─── MAX_AULAS_DIA ──────────────────────────────────────────────────────────

def _max_aulas(regras, ids_no_dia, ignorar=()):
    rows = [{'id': i} for i in ids_no_dia]
    conn = conn_roteirizado(cursor_com(rows=rows))
    A._validar_max_aulas_dia(conn, regras, 20, 40, 'Segunda', set(ignorar))


def test_max_aulas_dia_bloqueia_ao_estourar():
    with pytest.raises(A.ScheduleConflictError, match='no máximo 1'):
        _max_aulas([_regra(R.MAX_AULAS_DIA, {'quantidade': 1})], ids_no_dia=[100])


def test_max_aulas_dia_permite_dentro_do_limite():
    _max_aulas([_regra(R.MAX_AULAS_DIA, {'quantidade': 2})], ids_no_dia=[100])


def test_max_aulas_dia_ignora_a_propria_aula_que_esta_sendo_movida():
    _max_aulas([_regra(R.MAX_AULAS_DIA, {'quantidade': 1})], ids_no_dia=[100], ignorar=[100])


def test_max_aulas_dia_usa_o_limite_mais_restritivo():
    regras = [_regra(R.MAX_AULAS_DIA, {'quantidade': 3}), _regra(R.MAX_AULAS_DIA, {'quantidade': 1})]
    with pytest.raises(A.ScheduleConflictError, match='no máximo 1'):
        _max_aulas(regras, ids_no_dia=[100])


def test_max_aulas_dia_soft_nao_bloqueia():
    _max_aulas([_regra(R.MAX_AULAS_DIA, {'quantidade': 1}, obrigatoria=False)], ids_no_dia=[100])


def test_sem_regra_de_max_nao_consulta_o_banco():
    conn = conn_roteirizado()  # qualquer execute estouraria StopIteration
    A._validar_max_aulas_dia(conn, [], 20, 40, 'Segunda', set())


# ─── DIA_LIVRE / DISTRIBUIR_EM_N_DIAS ───────────────────────────────────────

def _dias_ocupados(regras, dias_existentes, novo_dia, ignorar=()):
    rows = [{'id': 100 + i, 'dia': d} for i, d in enumerate(dias_existentes)]
    conn = conn_roteirizado(cursor_com(rows=rows))
    A._validar_dias_ocupados(conn, regras, 30, novo_dia, set(ignorar))


def test_dia_livre_bloqueia_ao_ocupar_dia_demais():
    # 4 dias livres = o professor só pode trabalhar em 1 dia
    with pytest.raises(A.ScheduleConflictError, match='dia\\(s\\) livre'):
        _dias_ocupados([_regra(R.DIA_LIVRE, {'quantidade': 4})], ['Segunda'], 'Terça')


def test_dia_livre_permite_reforcar_um_dia_ja_usado():
    _dias_ocupados([_regra(R.DIA_LIVRE, {'quantidade': 4})], ['Segunda'], 'Segunda')


def test_distribuir_em_n_dias_bloqueia_o_dia_extra():
    with pytest.raises(A.ScheduleConflictError, match='Distribuir em 2'):
        _dias_ocupados([_regra(R.DISTRIBUIR_EM_N_DIAS, {'quantidade': 2})],
                       ['Segunda', 'Terça'], 'Quarta')


def test_distribuir_em_n_dias_permite_dentro_do_limite():
    _dias_ocupados([_regra(R.DISTRIBUIR_EM_N_DIAS, {'quantidade': 3})],
                   ['Segunda', 'Terça'], 'Quarta')


def test_dias_ocupados_ignora_a_aula_em_movimento():
    # a aula sai de Terça e vai para Quarta: continua sendo 2 dias, não 3
    _dias_ocupados([_regra(R.DISTRIBUIR_EM_N_DIAS, {'quantidade': 2})],
                   ['Segunda', 'Terça'], 'Quarta', ignorar=[101])


def test_dias_ocupados_soft_nao_bloqueia():
    _dias_ocupados([_regra(R.DIA_LIVRE, {'quantidade': 4}, obrigatoria=False)], ['Segunda'], 'Terça')


def test_sem_regra_de_dias_nao_consulta_o_banco():
    A._validar_dias_ocupados(conn_roteirizado(), [], 30, 'Segunda', set())


# ─── classificação de erros do MySQL ────────────────────────────────────────

def test_erro_1062_e_tratado_como_conflito_de_slot():
    erro = MagicMock()
    erro.errno = 1062
    assert A._is_duplicate_slot_error(erro)


def test_outros_errnos_nao_sao_conflito_de_slot():
    erro = MagicMock()
    erro.errno = 1146
    assert not A._is_duplicate_slot_error(erro)


@pytest.mark.parametrize('errno', [1205, 1213])
def test_deadlock_e_lock_timeout_sao_retentaveis(errno):
    erro = MagicMock()
    erro.errno = errno
    assert A._is_retryable_lock_error(erro)


def test_erro_generico_nao_e_retentavel():
    assert not A._is_retryable_lock_error(ValueError('qualquer coisa'))
