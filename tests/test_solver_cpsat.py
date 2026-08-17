"""Testes do solver CP-SAT (sem banco) — valida tradução das regras e geração de vagas."""
from solver import horario_cpsat as H
from models import regra_professor as R
from ortools.sat.python import cp_model


TURMAS = [{'id': 1, 'nome': '6A', 'aulas_por_dia': 5}]  # capacidade 25


def _prof(pid, nome, qtd, disc_id=10, disc_nome='Disc', dias=None, maxw=20, regras=None):
    return {
        'id': pid,
        'nome': nome,
        'dias_lista': dias or [],
        'max_aulas_semana': maxw,
        'cargas_lista': [{'turma_id': 1, 'disciplina_id': disc_id,
                          'disciplina_nome': disc_nome, 'aulas_semana': qtd}],
        'regras_lista': regras or [],
    }


def _regra(tipo, parametros, obrigatoria=True, peso=100, escopo=None):
    return {'tipo': tipo, 'parametros': parametros, 'obrigatoria': obrigatoria,
            'peso': peso, 'escopo_disciplina_id': escopo}


def _resolver(profs):
    demandas = H._construir_demandas(profs, {1: TURMAS[0]})
    solver, status, y, falta = H._resolver(demandas, TURMAS, permitir_vagas=True)
    return demandas, solver, status, y, falta


def _slots_do_prof(solver, y, idx):
    return [(d, p) for (i, d, p), v in y.items() if i == idx and solver.Value(v) == 1]


def test_alocacao_completa_sem_regras():
    profs = [_prof(1, 'A', 10, 10), _prof(2, 'B', 10, 11), _prof(3, 'C', 5, 12)]
    _, solver, status, y, falta = _resolver(profs)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    alocadas = sum(1 for v in y.values() if solver.Value(v) == 1)
    assert alocadas == 25
    assert sum(int(solver.Value(f)) for f in falta.values()) == 0


def test_dias_permitidos_gera_vagas():
    # A só pode segunda (5 slots) mas tem 10 aulas -> 5 vagas
    regras = [_regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']})]
    profs = [_prof(1, 'A', 10, 10, regras=regras), _prof(2, 'B', 10, 11), _prof(3, 'C', 5, 12)]
    demandas, solver, status, y, falta = _resolver(profs)
    assert int(solver.Value(falta[0])) == 5
    for (d, p) in _slots_do_prof(solver, y, 0):
        assert d == 'Segunda'


def test_dias_proibidos():
    regras = [_regra(R.DIAS_PROIBIDOS, {'dias': ['Sexta']})]
    profs = [_prof(1, 'A', 4, 10, regras=regras), _prof(2, 'B', 11, 11), _prof(3, 'C', 10, 12)]
    _, solver, status, y, _ = _resolver(profs)
    for (d, p) in _slots_do_prof(solver, y, 0):
        assert d != 'Sexta'


def test_periodo_fixo():
    regras = [_regra(R.PERIODO_FIXO, {'periodos': [1]})]
    profs = [_prof(1, 'A', 5, 10, regras=regras), _prof(2, 'B', 10, 11), _prof(3, 'C', 10, 12)]
    _, solver, status, y, _ = _resolver(profs)
    for (d, p) in _slots_do_prof(solver, y, 0):
        assert p == 1


def test_periodo_proibido_com_dia():
    # não pode 3º período na quarta
    regras = [_regra(R.PERIODO_PROIBIDO, {'periodos': [3], 'dias': ['Quarta']})]
    profs = [_prof(1, 'A', 10, 10, regras=regras), _prof(2, 'B', 10, 11), _prof(3, 'C', 5, 12)]
    _, solver, status, y, _ = _resolver(profs)
    for (d, p) in _slots_do_prof(solver, y, 0):
        assert not (d == 'Quarta' and p == 3)


def test_dia_livre():
    regras = [_regra(R.DIA_LIVRE, {'quantidade': 1})]
    profs = [_prof(1, 'A', 8, 10, regras=regras), _prof(2, 'B', 9, 11), _prof(3, 'C', 8, 12)]
    _, solver, status, y, _ = _resolver(profs)
    dias = {d for (d, p) in _slots_do_prof(solver, y, 0)}
    assert len(dias) <= 4  # deixou ao menos 1 dia livre


def test_distribuir_em_n_dias():
    regras = [_regra(R.DISTRIBUIR_EM_N_DIAS, {'quantidade': 2})]
    profs = [_prof(1, 'A', 8, 10, regras=regras), _prof(2, 'B', 9, 11), _prof(3, 'C', 8, 12)]
    _, solver, status, y, _ = _resolver(profs)
    dias = {d for (d, p) in _slots_do_prof(solver, y, 0)}
    assert len(dias) <= 2


def test_slot_fixo_primeiras():
    # 2 aulas nas duas primeiras da Quinta
    regras = [_regra(R.SLOT_FIXO, {'dia': 'Quinta', 'posicao': 'primeiras', 'quantidade': 2})]
    profs = [_prof(1, 'A', 2, 10, regras=regras), _prof(2, 'B', 13, 11), _prof(3, 'C', 10, 12)]
    _, solver, status, y, _ = _resolver(profs)
    slots = set(_slots_do_prof(solver, y, 0))
    assert slots == {('Quinta', 1), ('Quinta', 2)}


def test_contagem_por_dia():
    # 1 aula na Quinta, resto na Sexta (total 3)
    regras = [_regra(R.CONTAGEM_POR_DIA, {'distribuicao': {'Quinta': 1, 'Sexta': 'resto'}})]
    profs = [_prof(1, 'A', 3, 10, regras=regras), _prof(2, 'B', 12, 11), _prof(3, 'C', 10, 12)]
    _, solver, status, y, _ = _resolver(profs)
    slots = _slots_do_prof(solver, y, 0)
    quinta = [s for s in slots if s[0] == 'Quinta']
    sexta = [s for s in slots if s[0] == 'Sexta']
    outros = [s for s in slots if s[0] not in ('Quinta', 'Sexta')]
    assert len(quinta) == 1
    assert len(sexta) == 2
    assert outros == []


def test_max_aulas_dia_espalha():
    # A tem 10 aulas (numa turma de 5/dia) com limite de 2/dia -> no máx 2 por dia
    regras = [_regra(R.MAX_AULAS_DIA, {'quantidade': 2})]
    profs = [_prof(1, 'A', 10, 10, regras=regras), _prof(2, 'B', 10, 11), _prof(3, 'C', 5, 12)]
    demandas, solver, status, y, falta = _resolver(profs)
    por_dia = {}
    for (i, d, p), v in y.items():
        if i == 0 and solver.Value(v) == 1:
            por_dia[d] = por_dia.get(d, 0) + 1
    assert por_dia, 'A não foi alocado'
    assert max(por_dia.values()) <= 2, f'concentrou mais de 2/dia: {por_dia}'


def test_aula_geminada():
    # A tem 4 aulas com 1 bloco geminado -> deve existir um par em períodos consecutivos no mesmo dia
    regras = [_regra(R.AULA_GEMINADA, {'quantidade': 1})]
    profs = [_prof(1, 'A', 4, 10, regras=regras), _prof(2, 'B', 11, 11), _prof(3, 'C', 10, 12)]
    demandas, solver, status, y, falta = _resolver(profs)
    por_dia = {}
    for (i, d, p), v in y.items():
        if i == 0 and solver.Value(v) == 1:
            por_dia.setdefault(d, []).append(p)
    tem_par = any(
        any((p + 1) in pers for p in pers)
        for pers in por_dia.values()
    )
    assert tem_par, f'nenhum bloco geminado (2 seguidos) encontrado: {por_dia}'


def test_fallback_relaxa_estrutural_inviavel():
    # CONTAGEM exige Quinta, mas DIAS_PROIBIDOS bloqueia Quinta -> hard é inviável.
    # Com relaxar_estruturais=True deve voltar a ser viável (degrada para preferência).
    regras = [
        _regra(R.CONTAGEM_POR_DIA, {'distribuicao': {'Quinta': 1, 'Sexta': 'resto'}}),
        _regra(R.DIAS_PROIBIDOS, {'dias': ['Quinta']}),
    ]
    profs = [_prof(1, 'A', 2, 10, regras=regras), _prof(2, 'B', 13, 11), _prof(3, 'C', 10, 12)]
    dem = H._construir_demandas(profs, {1: TURMAS[0]})
    _, st_hard, _, _ = H._resolver(dem, TURMAS, permitir_vagas=True)
    _, st_soft, _, _ = H._resolver(dem, TURMAS, permitir_vagas=True, relaxar_estruturais=True)
    assert st_hard not in (cp_model.OPTIMAL, cp_model.FEASIBLE), 'esperava inviável no modo hard'
    assert st_soft in (cp_model.OPTIMAL, cp_model.FEASIBLE), 'fallback deveria viabilizar'


def test_contagem_soft_penaliza_sem_inviabilizar():
    # CONTAGEM como preferência não deve travar nem ser ignorada (antes era ignorada).
    regras = [_regra(R.CONTAGEM_POR_DIA, {'distribuicao': {'Quinta': 1, 'Sexta': 'resto'}}, obrigatoria=False)]
    profs = [_prof(1, 'A', 3, 10, regras=regras), _prof(2, 'B', 12, 11), _prof(3, 'C', 10, 12)]
    dem = H._construir_demandas(profs, {1: TURMAS[0]})
    _, st, _, _ = H._resolver(dem, TURMAS, permitir_vagas=True)
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_escopo_por_disciplina():
    # regra aplica só à disciplina 10; disciplina 99 do mesmo prof fica livre
    prof = {
        'id': 1, 'nome': 'A', 'dias_lista': [], 'max_aulas_semana': 20,
        'cargas_lista': [
            {'turma_id': 1, 'disciplina_id': 10, 'disciplina_nome': 'D10', 'aulas_semana': 3},
            {'turma_id': 1, 'disciplina_id': 99, 'disciplina_nome': 'D99', 'aulas_semana': 3},
        ],
        'regras_lista': [_regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']}, escopo=10)],
    }
    outro = _prof(2, 'B', 19, 11)
    demandas = H._construir_demandas([prof, outro], {1: TURMAS[0]})
    solver, status, y, falta = H._resolver(demandas, TURMAS, permitir_vagas=True)
    # demanda 0 = D10 (só segunda), demanda 1 = D99 (livre)
    d10 = [(d, p) for (i, d, p), v in y.items() if i == 0 and solver.Value(v) == 1]
    for (d, p) in d10:
        assert d == 'Segunda'


def test_ignorar_regras_de_libera_apenas_o_professor_alvo(monkeypatch):
    """A simulação "e se" relaxa as regras em memória — sem escrever no banco."""
    regras_a = [_regra(R.DIAS_PERMITIDOS, {'dias': ['Segunda']})]
    profs = [
        _prof(1, 'A', 10, 10, dias=['Segunda'], regras=regras_a),
        _prof(2, 'B', 5, 11, regras=[_regra(R.DIAS_PERMITIDOS, {'dias': ['Terça']})]),
    ]
    monkeypatch.setattr(H, 'listar_professores', lambda *a, **k: profs)
    monkeypatch.setattr(H, 'listar_turmas', lambda *a, **k: TURMAS)

    # A tem 10 aulas mas só pode segunda (5 períodos) -> 5 não cabem
    base = H.gerar_horario_cpsat(1, 'matutino', permitir_vagas=True, salvar=False)
    assert base['total'] == 10  # 5 de A na segunda + 5 de B na terça

    # relaxando A, as 10 aulas dele cabem; B continua preso à terça
    relaxado = H.gerar_horario_cpsat(1, 'matutino', permitir_vagas=True, salvar=False,
                                     ignorar_regras_de=[1])
    assert relaxado['total'] == 15
    assert profs[0]['regras_lista'] == regras_a, 'a lista original não pode ser mutada entre chamadas'


def test_ignorar_regras_de_nao_altera_o_padrao(monkeypatch):
    profs = [_prof(1, 'A', 4, 10, regras=[_regra(R.DIAS_PERMITIDOS, {'dias': ['Quarta']})])]
    monkeypatch.setattr(H, 'listar_professores', lambda *a, **k: profs)
    monkeypatch.setattr(H, 'listar_turmas', lambda *a, **k: TURMAS)

    resultado = H.gerar_horario_cpsat(1, 'matutino', permitir_vagas=True, salvar=False)
    assert resultado['total'] == 4
    assert resultado['aulas_salvas'] is False
