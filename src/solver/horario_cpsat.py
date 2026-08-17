"""Gerador de horários baseado em CP-SAT (Google OR-Tools).

Modela a alocação de aulas como um problema de satisfação de restrições:
- variáveis: y[(demanda, dia, periodo)] ∈ {0,1}
- restrições estruturais: exclusividade de turma e de professor, limite semanal
- regras por professor (ver models.regra_professor) traduzidas em restrições hard
  (ou penalidades, quando soft)
- objetivo: minimizar aulas vagas (prioridade máxima) e violações de regras soft

Quando uma demanda não cabe respeitando as regras hard, as aulas não alocadas
viram VAGAS (slots vazios persistidos), em vez de a geração inteira falhar.

Ver docs/spec-regras-e-aulas-vagas.md.
"""
import json
import logging
import os
from collections import defaultdict

from ortools.sat.python import cp_model

from database.connection import get_connection
from models.aula import salvar_aulas
from models.disciplina import listar_disciplinas  # noqa: F401 (mantido p/ paridade futura)
from models.professor import listar_professores
from models.turma import listar_turmas
from models.turno import normalizar_turno
from models import regra_professor as R
from utils.conflitos import DIAS

_LOGGER = logging.getLogger(__name__)

PESO_VAGA = 1000          # peso de cada aula vaga (domina o objetivo)
DEFAULT_MAX_SECONDS = 10


def _max_seconds():
    try:
        return max(1, int(os.getenv('SCHEDULER_MAX_SECONDS', str(DEFAULT_MAX_SECONDS))))
    except (TypeError, ValueError):
        return DEFAULT_MAX_SECONDS


def _periodos_turma(turma):
    return list(range(1, int(turma.get('aulas_por_dia') or 5) + 1))


def _slots_permitidos(dem):
    """Slots (dia, periodo) permitidos para a demanda sob as regras HARD.

    A tradução das regras em slots mora em models.regra_professor e é compartilhada
    com a edição manual da grade — gerar e arrastar precisam obedecer ao mesmo
    conjunto de regras, senão o primeiro arrasto desfaz o que o solver garantiu.
    """
    dias_base = set(dem['professor'].get('dias_lista') or DIAS)
    return R.slots_permitidos(dem['regras'], dem['periodos_turma'], dias_base)


def _construir_demandas(professores, turmas_por_id):
    demandas = []
    for prof in professores:
        for carga in prof.get('cargas_lista', []):
            turma_id = carga.get('turma_id')
            disciplina_id = carga.get('disciplina_id')
            qtd = int(carga.get('aulas_semana') or 0)
            if turma_id not in turmas_por_id or qtd <= 0:
                continue
            turma = turmas_por_id[turma_id]
            dem = {
                'professor': prof,
                'professor_id': prof['id'],
                'professor_nome': prof.get('nome'),
                'turma_id': turma_id,
                'turma_nome': turma.get('nome'),
                'disciplina_id': disciplina_id,
                'disciplina_nome': carga.get('disciplina_nome'),
                'qtd': qtd,
                'periodos_turma': _periodos_turma(turma),
                'regras': R.regras_aplicaveis(prof.get('regras_lista'), disciplina_id),
            }
            dem['slots'] = _slots_permitidos(dem)
            demandas.append(dem)
    return demandas


def _resolver(demandas, turmas, permitir_vagas, max_seconds=None, relaxar_estruturais=False):
    # relaxar_estruturais=True trata CONTAGEM_POR_DIA e AULA_GEMINADA obrigatórias como
    # preferência (penalidade) em vez de restrição dura — usado no fallback quando a
    # configuração hard é inviável, garantindo grade com vagas em vez de falha total.
    model = cp_model.CpModel()
    turmas_por_id = {t['id']: t for t in turmas}
    todos_periodos = sorted({p for t in turmas for p in _periodos_turma(t)})

    y = {}
    for i, dem in enumerate(demandas):
        for (dia, per) in dem['slots']:
            y[(i, dia, per)] = model.NewBoolVar(f'y_{i}_{dia}_{per}')

    objetivo = []
    falta = {}
    for i, dem in enumerate(demandas):
        qi = dem['qtd']
        falta[i] = model.NewIntVar(0, qi, f'falta_{i}')
        model.Add(sum(y[(i, d, p)] for (d, p) in dem['slots']) + falta[i] == qi)
        if not permitir_vagas:
            model.Add(falta[i] == 0)
        objetivo.append(PESO_VAGA * falta[i])

    # índices auxiliares
    dem_por_turma = {}
    dem_por_prof = {}
    for i, dem in enumerate(demandas):
        dem_por_turma.setdefault(dem['turma_id'], []).append(i)
        dem_por_prof.setdefault(dem['professor_id'], []).append(i)

    # exclusividade da turma: no máximo 1 aula por slot
    for turma_id, idxs in dem_por_turma.items():
        periodos = _periodos_turma(turmas_por_id[turma_id])
        for dia in DIAS:
            for per in periodos:
                aqui = [y[(i, dia, per)] for i in idxs if (i, dia, per) in y]
                if len(aqui) > 1:
                    model.Add(sum(aqui) <= 1)

    # exclusividade do professor + limite semanal + usado_dia
    usado = {}
    for prof_id, idxs in dem_por_prof.items():
        prof = demandas[idxs[0]]['professor']
        for dia in DIAS:
            for per in todos_periodos:
                aqui = [y[(i, dia, per)] for i in idxs if (i, dia, per) in y]
                if len(aqui) > 1:
                    model.Add(sum(aqui) <= 1)
            dia_vars = [y[(i, dia, per)] for i in idxs for per in todos_periodos if (i, dia, per) in y]
            b = model.NewBoolVar(f'usado_{prof_id}_{dia}')
            if dia_vars:
                model.AddMaxEquality(b, dia_vars)
            else:
                model.Add(b == 0)
            usado[(prof_id, dia)] = b

        max_semana = int(prof.get('max_aulas_semana') or 0)
        if max_semana > 0:
            todas = [y[(i, d, p)] for i in idxs for (d, p) in demandas[i]['slots']]
            if todas:
                model.Add(sum(todas) <= max_semana)

    # regras estruturais a nível de professor (DIA_LIVRE / DISTRIBUIR_EM_N_DIAS).
    # Obrigatória = limite rígido; preferência = penaliza usar mais dias que o permitido.
    for prof_id, idxs in dem_por_prof.items():
        prof = demandas[idxs[0]]['professor']
        usado_prof = [usado[(prof_id, dia)] for dia in DIAS]
        for regra in prof.get('regras_lista', []):
            tipo = regra['tipo']
            if tipo not in (R.DIA_LIVRE, R.DISTRIBUIR_EM_N_DIAS):
                continue
            p = regra.get('parametros') or {}
            if tipo == R.DIA_LIVRE:
                limite = len(DIAS) - int(p.get('quantidade') or 1)
            else:
                limite = int(p.get('quantidade') or 2)
            if regra.get('obrigatoria'):
                model.Add(sum(usado_prof) <= limite)
            else:
                excesso = model.NewIntVar(0, len(DIAS), f'estrut_exc_{prof_id}_{tipo}')
                model.Add(excesso >= sum(usado_prof) - limite)
                objetivo.append(int(regra.get('peso') or 100) * excesso)

    # CONTAGEM_POR_DIA hard: contagem fixa por dia, AGREGADA por professor (no escopo).
    # "1ª aula na quinta, as outras na sexta" refere-se ao conjunto de aulas do professor,
    # somando todas as turmas/demandas no escopo da regra.
    for prof_id, idxs in dem_por_prof.items():
        prof = demandas[idxs[0]]['professor']
        for regra in prof.get('regras_lista', []):
            if regra['tipo'] != R.CONTAGEM_POR_DIA:
                continue
            esc = regra.get('escopo_disciplina_id')
            idxs_escopo = [i for i in idxs if esc is None or int(demandas[i]['disciplina_id']) == int(esc)]
            qtd_total = sum(demandas[i]['qtd'] for i in idxs_escopo)
            distribuicao = (regra.get('parametros') or {}).get('distribuicao') or {}
            hard = regra.get('obrigatoria') and not relaxar_estruturais
            peso = int(regra.get('peso') or 100)
            for dia, valor in distribuicao.items():
                if valor == 'resto':
                    continue
                alvo = min(int(valor), qtd_total)
                vars_dia = [y[(i, dia, per)] for i in idxs_escopo
                            for per in demandas[i]['periodos_turma'] if (i, dia, per) in y]
                if hard:
                    model.Add(sum(vars_dia) == alvo)
                else:
                    desvio = model.NewIntVar(0, len(vars_dia) + alvo, f'cont_dev_{prof_id}_{dia}')
                    model.Add(desvio >= sum(vars_dia) - alvo)
                    model.Add(desvio >= alvo - sum(vars_dia))
                    objetivo.append(peso * desvio)

    # MAX_AULAS_DIA: limita aulas da demanda (turma+disciplina) por dia — espalha a matéria.
    for i, dem in enumerate(demandas):
        for regra in dem['regras']:
            if regra['tipo'] != R.MAX_AULAS_DIA:
                continue
            n = int((regra.get('parametros') or {}).get('quantidade') or 2)
            for dia in DIAS:
                vars_dia = [y[(i, dia, per)] for per in dem['periodos_turma'] if (i, dia, per) in y]
                if len(vars_dia) <= n:
                    continue
                if regra.get('obrigatoria'):
                    model.Add(sum(vars_dia) <= n)
                else:
                    excesso = model.NewIntVar(0, len(vars_dia), f'exc_dia_{i}_{dia}')
                    model.Add(excesso >= sum(vars_dia) - n)
                    objetivo.append(int(regra.get('peso') or 100) * excesso)

    # AULA_GEMINADA: força k blocos de 2 períodos consecutivos (mesmo dia) para a demanda.
    for i, dem in enumerate(demandas):
        for regra in dem['regras']:
            if regra['tipo'] != R.AULA_GEMINADA:
                continue
            k = int((regra.get('parametros') or {}).get('quantidade') or 1)
            k = min(k, dem['qtd'] // 2)  # não há como geminar mais pares do que metade da carga
            if k <= 0:
                continue
            periodos = dem['periodos_turma']
            blocos = []
            for dia in DIAS:
                for idx in range(len(periodos) - 1):
                    p1, p2 = periodos[idx], periodos[idx + 1]
                    if (i, dia, p1) in y and (i, dia, p2) in y:
                        b = model.NewBoolVar(f'gem_{i}_{dia}_{p1}')
                        model.Add(b <= y[(i, dia, p1)])
                        model.Add(b <= y[(i, dia, p2)])
                        blocos.append(b)
            if not blocos:
                continue
            if regra.get('obrigatoria') and not relaxar_estruturais:
                model.Add(sum(blocos) >= k)
            else:
                falta_g = model.NewIntVar(0, k, f'gem_falta_{i}')
                model.Add(falta_g >= k - sum(blocos))
                objetivo.append(int(regra.get('peso') or 100) * falta_g)

    # Penalidades de regras SOFT de pertinência (dia/período/slot fixo). Usa o mesmo
    # predicado das regras hard, para preferência e obrigação não divergirem.
    # CONTAGEM_POR_DIA fica de fora: já tem penalidade própria (desvio do alvo) acima,
    # e as demais (DIA_LIVRE, MAX_AULAS_DIA, AULA_GEMINADA...) também.
    for i, dem in enumerate(demandas):
        for regra in dem['regras']:
            if regra.get('obrigatoria') or regra['tipo'] == R.CONTAGEM_POR_DIA:
                continue
            peso = int(regra.get('peso') or 100)
            for (dia, per) in dem['slots']:
                if not R.regra_permite_slot(regra, dia, per, dem['periodos_turma']):
                    objetivo.append(peso * y[(i, dia, per)])

    if objetivo:
        model.Minimize(sum(objetivo))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_seconds if max_seconds else _max_seconds())
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 42
    status = solver.Solve(model)
    return solver, status, y, falta


def gerar_horario_cpsat(escola_id, turno=None, permitir_vagas=True, salvar=True, max_seconds=None,
                        ignorar_regras_de=None):
    """Gera a grade da escola/turno via CP-SAT e retorna o resultado estruturado.

    salvar=True persiste a grade (com lock). salvar=False apenas resolve e devolve o
    resultado, sem tocar no banco — usado pela análise de encaixes ("e se").

    ignorar_regras_de: ids de professores cujas regras devem ser desconsideradas
    nesta resolução. Vale só para esta chamada, em memória — a simulação "e se"
    não escreve nada no banco."""
    turno = normalizar_turno(turno)
    professores = listar_professores(escola_id, turno)
    if ignorar_regras_de:
        # Cópia rasa: relaxar não pode alterar os dicts recebidos de listar_professores.
        alvos = {int(pid) for pid in ignorar_regras_de}
        professores = [
            # dias_lista vazio = semana inteira liberada (ver _slots_permitidos)
            {**prof, 'regras_lista': [], 'dias_lista': []} if int(prof['id']) in alvos else prof
            for prof in professores
        ]
    turmas = listar_turmas(escola_id, turno)
    turmas_por_id = {t['id']: t for t in turmas}

    if not turmas:
        return {'status': 'vazio', 'mensagem': 'Cadastre ao menos uma turma antes de gerar o horário.',
                'total': 0, 'total_vagas': 0, 'diagnostico': [], 'aulas_salvas': False, 'solver_status': '-'}

    demandas = _construir_demandas(professores, turmas_por_id)
    if not demandas:
        return {'status': 'vazio', 'mensagem': 'Cadastre cargas (professor + turma + disciplina) antes de gerar.',
                'total': 0, 'total_vagas': 0, 'diagnostico': [], 'aulas_salvas': False, 'solver_status': '-'}

    solver, status, y, falta = _resolver(demandas, turmas, permitir_vagas, max_seconds=max_seconds)

    estruturais_relaxadas = False
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE) and permitir_vagas:
        # Fallback de robustez: uma regra estrutural obrigatória impossível (ex.: CONTAGEM_POR_DIA
        # ou AULA_GEMINADA conflitante) deixaria o turno inteiro inviável. Aqui as tratamos como
        # preferência e resolvemos de novo, garantindo uma grade (com vagas) + aviso.
        solver, status, y, falta = _resolver(
            demandas, turmas, permitir_vagas, max_seconds=max_seconds, relaxar_estruturais=True
        )
        estruturais_relaxadas = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            'status': 'inviavel',
            'mensagem': ('Não foi possível encontrar uma grade que respeite as regras obrigatórias. '
                         'Revise as regras dos professores ou habilite aulas vagas.'),
            'total': 0, 'total_vagas': 0, 'diagnostico': [],
            'aulas_salvas': False, 'solver_status': solver.StatusName(status),
        }

    # monta aulas reais
    aulas = []
    ocupados = {}  # turma_id -> set((dia,per))
    for (i, dia, per), var in y.items():
        if solver.Value(var) == 1:
            dem = demandas[i]
            aulas.append({
                'turma_id': dem['turma_id'],
                'professor_id': dem['professor_id'],
                'disciplina_id': dem['disciplina_id'],
                'dia': dia,
                'periodo': per,
                'vaga': 0,
            })
            ocupados.setdefault(dem['turma_id'], set()).add((dia, per))

    # diagnóstico das demandas não totalmente atendidas
    diagnostico = []
    motivo_por_turma = {}
    for i, dem in enumerate(demandas):
        faltantes = int(solver.Value(falta[i]))
        if faltantes <= 0:
            continue
        regras_desc = [R.descrever_regra(r) for r in dem['regras']]
        diagnostico.append({
            'professor_nome': dem['professor_nome'],
            'disciplina_nome': dem['disciplina_nome'],
            'turma_nome': dem['turma_nome'],
            'faltantes': faltantes,
            'regras': regras_desc,
            'explicacao': (f"Faltaram {faltantes} aula(s) de {dem['disciplina_nome']} "
                           f"com {dem['professor_nome']} na turma {dem['turma_nome']}"
                           + (f" — regras: {'; '.join(regras_desc)}." if regras_desc else ".")),
        })
        resumo = f"{dem['disciplina_nome']} ({dem['professor_nome']})"
        motivo_por_turma.setdefault(dem['turma_id'], []).append(resumo)

    # cria VAGAS nos slots de turma não ocupados
    total_vagas = 0
    for turma in turmas:
        periodos = _periodos_turma(turma)
        ocup = ocupados.get(turma['id'], set())
        motivo = motivo_por_turma.get(turma['id'])
        motivo_txt = ('Sem aula possível: ' + ', '.join(sorted(set(motivo)))[:200]) if motivo else 'Slot sem aula alocada'
        for dia in DIAS:
            for per in periodos:
                if (dia, per) not in ocup:
                    aulas.append({
                        'turma_id': turma['id'],
                        'professor_id': None,
                        'disciplina_id': None,
                        'dia': dia,
                        'periodo': per,
                        'vaga': 1,
                        'motivo_vaga': motivo_txt,
                    })
                    total_vagas += 1

    total_reais = len(aulas) - total_vagas
    total_falta = sum(int(it['faltantes']) for it in diagnostico)
    # Aulas não alocadas por falta de espaço (turma cheia, demanda > capacidade): não viram VAGA.
    sobra = max(0, total_falta - total_vagas)

    # salva com lock de aplicação por (escola, turno) para evitar corrida TOCTOU
    if salvar:
        _salvar_com_lock(escola_id, aulas, turno)

    if total_vagas == 0 and total_falta == 0:
        status_txt = 'ok'
        mensagem = f'Horário gerado com sucesso ({total_reais} aulas). Todas as regras foram respeitadas.'
    else:
        status_txt = 'ok_com_vagas'
        partes = [f'{total_reais} aula(s) alocada(s)']
        if total_vagas:
            partes.append(f'{total_vagas} vaga(s)')
        if sobra:
            partes.append(f'{sobra} aula(s) sem espaço (demanda acima da capacidade da turma)')
        mensagem = 'Horário gerado: ' + ', '.join(partes) + '. Veja o diagnóstico.'

    if estruturais_relaxadas:
        status_txt = 'ok_com_vagas'
        mensagem += (' Atenção: alguma regra estrutural obrigatória (contagem por dia / aula '
                     'geminada) era impossível e foi tratada como preferência para viabilizar a grade.')

    return {
        'status': status_txt,
        'mensagem': mensagem,
        'total': total_reais,
        'total_vagas': total_vagas,
        'diagnostico': diagnostico,
        'estruturais_relaxadas': estruturais_relaxadas,
        'aulas_salvas': bool(salvar),
        'solver_status': solver.StatusName(status),
    }


def _salvar_com_lock(escola_id, aulas, turno):
    lock_name = f'flowter:grade:{escola_id}:{turno}'
    lock_conn = get_connection()
    adquiriu = False
    try:
        row = lock_conn.execute("SELECT GET_LOCK(%s, 30) AS ok", (lock_name,)).fetchone()
        adquiriu = bool(row and int(row.get('ok') or 0) == 1)
        salvar_aulas(escola_id, aulas, turno=turno)
    finally:
        if adquiriu:
            try:
                lock_conn.execute("SELECT RELEASE_LOCK(%s)", (lock_name,)).fetchone()
            except Exception:
                _LOGGER.exception('Falha ao liberar lock da grade %s/%s.', escola_id, turno)
        lock_conn.close()


def _parse_par(v):
    if isinstance(v, dict):
        return v
    if isinstance(v, (bytes, bytearray)):
        v = v.decode('utf-8')
    try:
        return json.loads(v) if v else {}
    except (TypeError, ValueError):
        return {}


def analisar_encaixes(escola_id, turno=None, max_culpados=6, max_seconds=10):
    """Analisa a grade salva: conflitos, vagas e simulações 'e se' (relaxar regras de
    cada professor que gerou vaga, medindo quantas aulas voltariam a encaixar).
    Não altera a grade salva (as simulações rodam com salvar=False)."""
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        aulas = conn.execute(
            "SELECT professor_id,turma_id,disciplina_id,dia,periodo,vaga FROM aulas WHERE escola_id=%s AND turno=%s",
            (escola_id, turno),
        ).fetchall()
        reais = [a for a in aulas if not a['vaga']]
        total_vagas = sum(1 for a in aulas if a['vaga'])

        # conflitos estruturais (devem ser 0)
        prof_slot = defaultdict(int); turma_slot = defaultdict(int)
        for a in reais:
            prof_slot[(a['professor_id'], a['dia'], a['periodo'])] += 1
            turma_slot[(a['turma_id'], a['dia'], a['periodo'])] += 1
        conflito_prof = sum(1 for v in prof_slot.values() if v > 1)
        conflito_turma = sum(1 for v in turma_slot.values() if v > 1)

        # falta por professor: carga cadastrada menos aulas efetivamente colocadas
        cargas = conn.execute(
            """SELECT pc.professor_id, pc.turma_id, pc.disciplina_id, pc.aulas_semana, p.nome prof
               FROM professores_cargas pc
               JOIN professores p ON p.id = pc.professor_id
               WHERE p.escola_id=%s AND p.turno=%s""",
            (escola_id, turno),
        ).fetchall()
        colocadas = defaultdict(int)
        for a in reais:
            colocadas[(a['professor_id'], a['turma_id'], a['disciplina_id'])] += 1
        falta_prof = defaultdict(int); nome_prof = {}
        for c in cargas:
            f = int(c['aulas_semana']) - colocadas.get((c['professor_id'], c['turma_id'], c['disciplina_id']), 0)
            if f > 0:
                falta_prof[c['professor_id']] += f
                nome_prof[c['professor_id']] = c['prof']

        culpados = []
        for pid, f in sorted(falta_prof.items(), key=lambda x: -x[1])[:max_culpados]:
            regras = conn.execute(
                "SELECT tipo,parametros,obrigatoria,escopo_disciplina_id FROM professores_regras WHERE professor_id=%s AND ativa=1",
                (pid,),
            ).fetchall()
            tem_obrig = any(r['obrigatoria'] for r in regras)
            desc = [R.descrever_regra({'tipo': r['tipo'], 'parametros': _parse_par(r['parametros']),
                                       'escopo_disciplina_nome': None})
                    for r in regras if r['obrigatoria']]
            culpados.append({'professor_id': pid, 'nome': nome_prof[pid], 'faltantes': f,
                             'regras': desc, 'tem_obrigatoria': tem_obrig, 'recupera': 0})

        # Simulação "e se" — relaxa as regras do professor e re-resolve, tudo em
        # memória. Antes isso era feito com UPDATE ativa=0 / ativa=1 no banco: se o
        # processo morresse no meio da resolução, as regras ficavam desativadas de
        # forma permanente e silenciosa. Nenhuma escrita aqui, nenhuma janela de risco.
        for c in culpados:
            if not c['tem_obrigatoria']:
                continue
            r = gerar_horario_cpsat(
                escola_id, turno, permitir_vagas=True, salvar=False,
                max_seconds=max_seconds, ignorar_regras_de=[c['professor_id']],
            )
            c['recupera'] = max(0, total_vagas - r['total_vagas'])

        return {
            'conflito_professor': conflito_prof,
            'conflito_turma': conflito_turma,
            'total_vagas': total_vagas,
            'total_reais': len(reais),
            'culpados': culpados,
        }
    finally:
        conn.close()
