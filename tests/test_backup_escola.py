"""Fidelidade da cópia oculta de escola (duplicar_escola_oculta).

As regras dos professores fazem parte da grade: sem elas, o backup restaurado
geraria um horário diferente do original.
"""
import json

from models import escola as E


def test_parametros_json_de_dict():
    assert json.loads(E._parametros_regra_json({'dias': ['Segunda']})) == {'dias': ['Segunda']}


def test_parametros_json_de_lista():
    assert json.loads(E._parametros_regra_json([1, 2])) == [1, 2]


def test_parametros_json_de_bytes():
    bruto = bytearray(b'{"dias": ["Sexta"]}')
    assert json.loads(E._parametros_regra_json(bruto)) == {'dias': ['Sexta']}


def test_parametros_json_de_string_passa_direto():
    assert E._parametros_regra_json('{"quantidade": 2}') == '{"quantidade": 2}'


def test_parametros_json_vazio_vira_objeto_vazio():
    # a coluna é NOT NULL: valor irrecuperável não pode quebrar a cópia
    assert E._parametros_regra_json(None) == '{}'
    assert E._parametros_regra_json('') == '{}'
    assert E._parametros_regra_json('   ') == '{}'
