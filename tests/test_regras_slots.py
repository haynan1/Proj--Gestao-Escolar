"""Tradução regra -> slot permitido.

Fonte única consumida pelo solver (solver.horario_cpsat) e pela edição manual da
grade (models.aula): gerar o horário e arrastar uma aula precisam obedecer às
mesmas regras, senão o primeiro arrasto desfaz o que a geração garantiu.
"""
import pytest

from models import regra_professor as R
from utils.conflitos import DIAS

PERIODOS = [1, 2, 3, 4, 5]


def regra(tipo, parametros, obrigatoria=True, escopo=None):
    return {'tipo': tipo, 'parametros': parametros, 'obrigatoria': obrigatoria,
            'escopo_disciplina_id': escopo}


def bloqueia(regras, dia, periodo, periodos=PERIODOS):
    return R.regra_que_bloqueia_slot(regras, dia, periodo, periodos) is not None


# ─── pertinência por dia ────────────────────────────────────────────────────

def test_dias_permitidos():
    r = [regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda', 'Quarta']})]
    assert not bloqueia(r, 'Segunda', 1)
    assert bloqueia(r, 'Terça', 1)


def test_dias_proibidos():
    r = [regra(R.DIAS_PROIBIDOS, {'dias': ['Sexta']})]
    assert not bloqueia(r, 'Quinta', 1)
    assert bloqueia(r, 'Sexta', 1)


# ─── pertinência por período ────────────────────────────────────────────────

def test_periodo_fixo():
    r = [regra(R.PERIODO_FIXO, {'periodos': [1, 2]})]
    assert not bloqueia(r, 'Segunda', 2)
    assert bloqueia(r, 'Segunda', 3)


def test_periodo_proibido_em_todos_os_dias():
    r = [regra(R.PERIODO_PROIBIDO, {'periodos': [5]})]
    assert bloqueia(r, 'Segunda', 5)
    assert bloqueia(r, 'Sexta', 5)
    assert not bloqueia(r, 'Segunda', 4)


def test_periodo_proibido_restrito_a_dias():
    r = [regra(R.PERIODO_PROIBIDO, {'periodos': [1], 'dias': ['Segunda']})]
    assert bloqueia(r, 'Segunda', 1)
    assert not bloqueia(r, 'Terça', 1), 'a proibição vazou para um dia fora do escopo'
    assert not bloqueia(r, 'Segunda', 2)


# ─── slot fixo ──────────────────────────────────────────────────────────────

def test_slot_fixo_primeiras():
    r = [regra(R.SLOT_FIXO, {'dia': 'Quinta', 'posicao': 'primeiras', 'quantidade': 2})]
    assert not bloqueia(r, 'Quinta', 1)
    assert not bloqueia(r, 'Quinta', 2)
    assert bloqueia(r, 'Quinta', 3)
    assert bloqueia(r, 'Sexta', 1), 'slot fixo deveria prender o dia também'


def test_slot_fixo_ultimas():
    r = [regra(R.SLOT_FIXO, {'dia': 'Terça', 'posicao': 'ultimas', 'quantidade': 1})]
    assert not bloqueia(r, 'Terça', 5)
    assert bloqueia(r, 'Terça', 4)


def test_slot_fixo_periodos_explicitos():
    r = [regra(R.SLOT_FIXO, {'dia': 'Terça', 'posicao': 'periodos', 'periodos': [2, 4]})]
    assert not bloqueia(r, 'Terça', 4)
    assert bloqueia(r, 'Terça', 3)


def test_slot_fixo_ultimas_com_quantidade_zero_nao_libera_nada():
    r = [regra(R.SLOT_FIXO, {'dia': 'Terça', 'posicao': 'ultimas', 'quantidade': 0})]
    assert bloqueia(r, 'Terça', 5)


# ─── contagem por dia ───────────────────────────────────────────────────────

def test_contagem_por_dia_restringe_os_dias():
    r = [regra(R.CONTAGEM_POR_DIA, {'distribuicao': {'Quinta': 1, 'Sexta': 'resto'}})]
    assert not bloqueia(r, 'Quinta', 1)
    assert bloqueia(r, 'Segunda', 1)


# ─── regras de cardinalidade não decidem pertinência ────────────────────────

@pytest.mark.parametrize('tipo', [R.MAX_AULAS_DIA, R.AULA_GEMINADA,
                                  R.DIA_LIVRE, R.DISTRIBUIR_EM_N_DIAS])
def test_regras_de_quantidade_nao_bloqueiam_slot_isolado(tipo):
    assert not bloqueia([regra(tipo, {'quantidade': 1})], 'Segunda', 1)


# ─── hard x soft ────────────────────────────────────────────────────────────

def test_regra_de_preferencia_nunca_bloqueia():
    r = [regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}, obrigatoria=False)]
    assert not bloqueia(r, 'Sexta', 1)


def test_a_regra_devolvida_e_a_que_bloqueou():
    r = [
        regra(R.DIAS_PROIBIDOS, {'dias': ['Sexta']}),
        regra(R.PERIODO_FIXO, {'periodos': [1]}),
    ]
    bloqueio = R.regra_que_bloqueia_slot(r, 'Segunda', 3, PERIODOS)
    assert bloqueio['tipo'] == R.PERIODO_FIXO
    assert 'período' in R.descrever_regra(bloqueio).lower()


def test_regras_se_acumulam():
    r = [
        regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda', 'Terça']}),
        regra(R.PERIODO_PROIBIDO, {'periodos': [1]}),
    ]
    assert not bloqueia(r, 'Terça', 2)
    assert bloqueia(r, 'Terça', 1)
    assert bloqueia(r, 'Quarta', 2)


# ─── slots_permitidos ───────────────────────────────────────────────────────

def test_sem_regras_todos_os_slots_valem():
    assert len(R.slots_permitidos([], PERIODOS)) == len(DIAS) * len(PERIODOS)


def test_slots_permitidos_respeita_os_dias_base_do_professor():
    slots = R.slots_permitidos([], PERIODOS, dias_base={'Segunda'})
    assert {dia for dia, _ in slots} == {'Segunda'}


def test_slots_permitidos_mantem_a_ordem_canonica():
    slots = R.slots_permitidos([], [1, 2])
    assert slots[:3] == [('Segunda', 1), ('Segunda', 2), ('Terça', 1)]


def test_regras_contraditorias_zeram_os_slots():
    r = [
        regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}),
        regra(R.DIAS_PROIBIDOS, {'dias': ['Segunda']}),
    ]
    assert R.slots_permitidos(r, PERIODOS) == []


# ─── escopo por disciplina ──────────────────────────────────────────────────

def test_regra_global_vale_para_qualquer_disciplina():
    r = [regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']})]
    assert R.regras_aplicaveis(r, 7) == r
    assert R.regras_aplicaveis(r, None) == r


def test_regra_de_disciplina_so_vale_para_ela():
    r = [regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}, escopo=7)]
    assert R.regras_aplicaveis(r, 7) == r
    assert R.regras_aplicaveis(r, 9) == []


def test_regra_de_disciplina_nao_vale_quando_a_disciplina_e_desconhecida():
    r = [regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}, escopo=7)]
    assert R.regras_aplicaveis(r, None) == []
