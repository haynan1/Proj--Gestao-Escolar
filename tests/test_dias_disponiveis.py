"""Disponibilidade semanal do professor derivada das regras.

O cadastro do professor não edita mais `dias_disponiveis`: a coluna virou cache
derivado das regras de dia (DIAS_PERMITIDOS / DIAS_PROIBIDOS), que passaram a ser
a única fonte de verdade. Estes testes fixam esse contrato.
"""
import json
from unittest.mock import MagicMock

import pytest

from models import professor as P
from models import regra_professor as R
from utils.conflitos import DIAS


def make_mock_conn(row=None, rows=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    cursor.fetchall.return_value = rows if rows is not None else []
    cursor.lastrowid = 1
    cursor.rowcount = 0
    conn = MagicMock()
    conn.execute.return_value = cursor
    return conn


def _regra(tipo, dias, obrigatoria=True, escopo=None):
    return {
        'tipo': tipo,
        'parametros': {'dias': dias},
        'obrigatoria': obrigatoria,
        'escopo_disciplina_id': escopo,
    }


# ─── dias_efetivos ──────────────────────────────────────────────────────────

def test_sem_regras_professor_livre_na_semana():
    assert R.dias_efetivos([]) == list(DIAS)


def test_dias_permitidos_restringe():
    assert R.dias_efetivos([_regra(R.DIAS_PERMITIDOS, ['Segunda'])]) == ['Segunda']


def test_dias_proibidos_subtrai():
    assert R.dias_efetivos([_regra(R.DIAS_PROIBIDOS, ['Sexta'])]) == \
        ['Segunda', 'Terça', 'Quarta', 'Quinta']


def test_permitidos_e_proibidos_se_combinam():
    regras = [
        _regra(R.DIAS_PERMITIDOS, ['Segunda', 'Terça', 'Quarta']),
        _regra(R.DIAS_PROIBIDOS, ['Terça']),
    ]
    assert R.dias_efetivos(regras) == ['Segunda', 'Quarta']


def test_resultado_segue_a_ordem_canonica_da_semana():
    assert R.dias_efetivos([_regra(R.DIAS_PERMITIDOS, ['Sexta', 'Segunda'])]) == ['Segunda', 'Sexta']


def test_regra_de_preferencia_nao_restringe():
    # Soft entra como penalidade no solver, não como bloqueio de disponibilidade.
    regras = [_regra(R.DIAS_PERMITIDOS, ['Segunda'], obrigatoria=False)]
    assert R.dias_efetivos(regras) == list(DIAS)


def test_regra_com_escopo_de_disciplina_nao_restringe_o_professor():
    # Vale só para a demanda daquela disciplina — o professor segue livre nos demais dias.
    regras = [_regra(R.DIAS_PERMITIDOS, ['Segunda'], escopo=7)]
    assert R.dias_efetivos(regras) == list(DIAS)


def test_regras_contraditorias_zeram_a_disponibilidade():
    regras = [
        _regra(R.DIAS_PERMITIDOS, ['Segunda']),
        _regra(R.DIAS_PROIBIDOS, ['Segunda']),
    ]
    assert R.dias_efetivos(regras) == []


def test_outros_tipos_de_regra_nao_afetam_os_dias():
    regras = [{'tipo': R.AULA_GEMINADA, 'parametros': {'quantidade': 1},
               'obrigatoria': True, 'escopo_disciplina_id': None}]
    assert R.dias_efetivos(regras) == list(DIAS)


# ─── dias_efetivos_de_linhas / sincronizar_dias_disponiveis ─────────────────

def test_linhas_cruas_com_parametros_em_json():
    linhas = [{'tipo': R.DIAS_PERMITIDOS, 'parametros': json.dumps({'dias': ['Quarta']}),
               'obrigatoria': 1, 'escopo_disciplina_id': None}]
    assert R.dias_efetivos_de_linhas(linhas) == ['Quarta']


def test_sincronizar_grava_dias_derivados_na_coluna():
    linhas = [{'tipo': R.DIAS_PROIBIDOS, 'parametros': json.dumps({'dias': ['Segunda']}),
               'obrigatoria': 1, 'escopo_disciplina_id': None}]
    conn = make_mock_conn(rows=linhas)

    dias = R.sincronizar_dias_disponiveis(conn, 42)

    assert dias == ['Terça', 'Quarta', 'Quinta', 'Sexta']
    update = [c for c in conn.execute.call_args_list if 'UPDATE professores' in c.args[0]]
    assert len(update) == 1
    assert update[0].args[1] == ('Terça,Quarta,Quinta,Sexta', 42)


def test_sincronizar_sem_regras_libera_a_semana_inteira():
    conn = make_mock_conn(rows=[])
    assert R.sincronizar_dias_disponiveis(conn, 7) == list(DIAS)


def test_sincronizar_escopa_a_escrita_por_escola_e_turno():
    # professor_id chega de parâmetro de rota em alguns fluxos: sem o escopo,
    # a atualização alcançaria professor de outra escola.
    conn = make_mock_conn(rows=[])
    R.sincronizar_dias_disponiveis(conn, 7, escola_id=3, turno='matutino')

    update = [c for c in conn.execute.call_args_list if 'UPDATE professores' in c.args[0]][0]
    assert 'escola_id = %s' in update.args[0]
    assert 'turno = %s' in update.args[0]
    assert update.args[1] == (','.join(DIAS), 7, 3, 'matutino')


def test_sincronizar_usa_apenas_regras_ativas():
    conn = make_mock_conn(rows=[])
    R.sincronizar_dias_disponiveis(conn, 7)
    select = [c for c in conn.execute.call_args_list if 'professores_regras' in c.args[0]][0]
    assert 'ativa = 1' in select.args[0]


# ─── atualizar_professor: dias fora do formulário ───────────────────────────

def _conn_para_atualizacao(monkeypatch):
    conn = make_mock_conn(row={'total': 0})
    monkeypatch.setattr(P, 'get_connection', lambda: conn)
    monkeypatch.setattr(P, '_professor_nome_existe', lambda *a, **k: False)
    for nome in ('_sincronizar_disciplinas_professor', '_sincronizar_turmas_professor',
                 '_sincronizar_cargas_professor'):
        monkeypatch.setattr(P, nome, lambda *a, **k: None)
    return conn


def _update_professores(conn):
    return [c for c in conn.execute.call_args_list if c.args[0].strip().startswith('UPDATE professores')]


def test_atualizar_sem_dias_nao_toca_na_coluna(monkeypatch):
    conn = _conn_para_atualizacao(monkeypatch)

    P.atualizar_professor(1, 2, 'Ana', ['3'], 10, None, ['4'], None, '#22c55e', 'matutino')

    updates = _update_professores(conn)
    assert len(updates) == 1
    assert 'dias_disponiveis' not in updates[0].args[0]


def test_atualizar_sem_dias_nao_valida_conflito_de_aulas(monkeypatch):
    conn = _conn_para_atualizacao(monkeypatch)

    P.atualizar_professor(1, 2, 'Ana', ['3'], 10, None, ['4'], None, '#22c55e', 'matutino')

    assert not [c for c in conn.execute.call_args_list if 'FROM aulas' in c.args[0]]


def test_atualizar_com_dias_explicitos_ainda_grava_e_valida(monkeypatch):
    # O caminho continua disponível para chamadas internas (migração/backfill).
    conn = _conn_para_atualizacao(monkeypatch)

    P.atualizar_professor(1, 2, 'Ana', ['3'], 10, ['Segunda'], ['4'], None, '#22c55e', 'matutino')

    updates = _update_professores(conn)
    assert 'dias_disponiveis' in updates[0].args[0]
    assert [c for c in conn.execute.call_args_list if 'FROM aulas' in c.args[0]]


def test_atualizar_com_dias_bloqueia_quando_ha_aula_em_dia_removido(monkeypatch):
    conn = _conn_para_atualizacao(monkeypatch)
    conn.execute.return_value = MagicMock(
        fetchone=MagicMock(return_value={'total': 3}),
        fetchall=MagicMock(return_value=[]),
        lastrowid=1,
        rowcount=0,
    )

    with pytest.raises(ValueError, match='3 aula'):
        P.atualizar_professor(1, 2, 'Ana', ['3'], 10, ['Segunda'], ['4'], None, '#22c55e', 'matutino')
