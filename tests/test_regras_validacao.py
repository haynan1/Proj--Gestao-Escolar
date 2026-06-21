"""Testes de validação/normalização das regras por professor."""
import pytest

from models import regra_professor as R


def test_dias_permitidos_normaliza_ordem():
    out = R.normalizar_parametros(R.DIAS_PERMITIDOS, {'dias': ['Sexta', 'Segunda']})
    assert out == {'dias': ['Segunda', 'Sexta']}


def test_dias_permitidos_vazio_invalido():
    with pytest.raises(R.RegraValidationError):
        R.normalizar_parametros(R.DIAS_PERMITIDOS, {'dias': []})


def test_dia_livre_limite():
    assert R.normalizar_parametros(R.DIA_LIVRE, {'quantidade': 1}) == {'quantidade': 1}
    with pytest.raises(R.RegraValidationError):
        R.normalizar_parametros(R.DIA_LIVRE, {'quantidade': 5})  # não dá pra deixar todos livres


def test_periodo_fixo_exige_periodo():
    assert R.normalizar_parametros(R.PERIODO_FIXO, {'periodos': [6, 6, 1]}) == {'periodos': [1, 6]}
    with pytest.raises(R.RegraValidationError):
        R.normalizar_parametros(R.PERIODO_FIXO, {'periodos': []})


def test_periodo_proibido_com_dias():
    out = R.normalizar_parametros(R.PERIODO_PROIBIDO, {'periodos': [3], 'dias': ['Quarta']})
    assert out == {'periodos': [3], 'dias': ['Quarta']}


def test_slot_fixo_primeiras():
    out = R.normalizar_parametros(R.SLOT_FIXO, {'dia': 'Quinta', 'posicao': 'primeiras', 'quantidade': 2})
    assert out['dia'] == 'Quinta' and out['posicao'] == 'primeiras' and out['quantidade'] == 2


def test_slot_fixo_dia_invalido():
    with pytest.raises(R.RegraValidationError):
        R.normalizar_parametros(R.SLOT_FIXO, {'dia': 'Sabado', 'posicao': 'primeiras', 'quantidade': 1})


def test_contagem_por_dia():
    out = R.normalizar_parametros(R.CONTAGEM_POR_DIA, {'distribuicao': {'Quinta': '1', 'Sexta': 'resto'}})
    assert out == {'distribuicao': {'Quinta': 1, 'Sexta': 'resto'}}


def test_max_aulas_dia():
    assert R.normalizar_parametros(R.MAX_AULAS_DIA, {'quantidade': 2}) == {'quantidade': 2}
    with pytest.raises(R.RegraValidationError):
        R.normalizar_parametros(R.MAX_AULAS_DIA, {'quantidade': 0})


def test_aula_geminada():
    assert R.normalizar_parametros(R.AULA_GEMINADA, {'quantidade': 1}) == {'quantidade': 1}
    with pytest.raises(R.RegraValidationError):
        R.normalizar_parametros(R.AULA_GEMINADA, {'quantidade': 0})


def test_descrever_regra():
    regra = {'tipo': R.DIAS_PERMITIDOS, 'parametros': {'dias': ['Segunda', 'Terça']},
             'escopo_disciplina_nome': None}
    assert 'Segunda' in R.descrever_regra(regra)
