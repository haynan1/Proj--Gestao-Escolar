import random
from collections import defaultdict
from utils.conflitos import (
    DIAS,
    verificar_conflito_professor,
    verificar_conflito_turma,
    verificar_aulas_seguidas,
    contar_aulas_professor
)
from models.professor import listar_professores
from models.turma import listar_turmas
from models.disciplina import listar_disciplinas
from models.aula import listar_aulas, salvar_aulas


MAX_TENTATIVAS_GRADE = 100


def _nova_semente_aleatoria():
    return random.SystemRandom().randrange(1, 2**63)


def _demandas_detalhadas(professores, turmas, disciplinas):
    turma_ids = {turma['id'] for turma in turmas}
    disciplinas_por_id = {disciplina['id']: disciplina for disciplina in disciplinas}
    demandas = []

    for professor in professores:
        for carga in professor.get('cargas_lista', []):
            turma_id = carga.get('turma_id')
            disciplina_id = carga.get('disciplina_id')
            qtd = int(carga.get('aulas_semana') or 0)
            if turma_id not in turma_ids or disciplina_id not in disciplinas_por_id or qtd <= 0:
                continue

            demandas.append({
                'turma_id': turma_id,
                'disciplina': disciplinas_por_id[disciplina_id],
                'professor': professor,
                'qtd': qtd,
            })

    return demandas


def _periodos_turma(turma):
    aulas_por_dia = int(turma.get('aulas_por_dia') or 5)
    return list(range(1, aulas_por_dia + 1))


def _capacidade_turma(turma):
    return len(DIAS) * len(_periodos_turma(turma))


def _validar_capacidade_demandas(demandas, turmas):
    turmas_por_id = {turma['id']: turma for turma in turmas}
    demanda_por_turma = defaultdict(int)
    demanda_por_professor = defaultdict(int)
    professores_por_id = {}

    for demanda in demandas:
        demanda_por_turma[demanda['turma_id']] += demanda['qtd']
        professor = demanda['professor']
        professores_por_id[professor['id']] = professor
        demanda_por_professor[professor['id']] += demanda['qtd']

    erros = []
    for turma in turmas:
        turma_id = turma['id']
        demanda_total = demanda_por_turma.get(turma_id, 0)
        turma = turmas_por_id[turma_id]
        capacidade = _capacidade_turma(turma)
        if demanda_total > capacidade:
            erros.append(
                f"{turma['nome']}: excede {demanda_total - capacidade} aula(s) "
                f"({demanda_total} configuradas para {capacidade} horários)"
            )
        elif demanda_total < capacidade:
            erros.append(
                f"{turma['nome']}: faltam {capacidade - demanda_total} aula(s) "
                f"({demanda_total} configuradas para {capacidade} horários)"
            )

    for professor_id, demanda_total in sorted(demanda_por_professor.items()):
        professor = professores_por_id[professor_id]
        max_aulas = int(professor.get('max_aulas_semana') or 0)
        if max_aulas > 0 and demanda_total > max_aulas:
            erros.append(
                f"{professor['nome']}: {demanda_total} aulas configuradas para limite de {max_aulas}"
            )

    return erros


def _ordenar_demandas(demandas, turmas, rng):
    turmas_por_id = {turma['id']: turma for turma in turmas}
    demanda_por_turma = defaultdict(int)
    demanda_por_professor = defaultdict(int)

    for demanda in demandas:
        demanda_por_turma[demanda['turma_id']] += demanda['qtd']
        demanda_por_professor[demanda['professor']['id']] += demanda['qtd']

    ordenadas = list(demandas)
    rng.shuffle(ordenadas)
    ordenadas.sort(
        key=lambda demanda: (
            _capacidade_turma(turmas_por_id[demanda['turma_id']]) - demanda_por_turma[demanda['turma_id']],
            len(demanda['professor'].get('dias_lista', [])),
            -demanda_por_professor[demanda['professor']['id']],
            -demanda['qtd'],
        )
    )
    return ordenadas


def _alocar_demanda(grade, turma, disc, qtd, professores_disponiveis, tentativas_max, rng):
    turma_id = turma['id']
    periodos = _periodos_turma(turma)
    disc_id = disc['id']
    colocadas = 0
    tentativas = 0

    slots = [(d, p) for d in DIAS for p in periodos]
    rng.shuffle(slots)

    for (dia, periodo) in slots:
        if colocadas >= qtd:
            break
        if tentativas > tentativas_max:
            break
        tentativas += 1

        if verificar_conflito_turma(grade, turma_id, dia, periodo):
            continue

        if verificar_aulas_seguidas(grade, turma_id, disc_id, dia, periodo, max(periodos)):
            continue

        profs_shuffled = professores_disponiveis.copy()
        rng.shuffle(profs_shuffled)

        for prof in profs_shuffled:
            if dia not in prof['dias_lista']:
                continue

            if verificar_conflito_professor(grade, prof['id'], dia, periodo):
                continue

            max_aulas_semana = int(prof.get('max_aulas_semana') or 0)
            if max_aulas_semana > 0 and contar_aulas_professor(grade, prof['id']) >= max_aulas_semana:
                continue

            grade[turma_id][(dia, periodo)] = {
                'professor_id': prof['id'],
                'disciplina_id': disc_id,
                'professor_nome': prof['nome'],
                'disciplina_nome': disc['nome'],
                'disciplina_cor': disc['cor'],
            }
            colocadas += 1
            break

    return colocadas


def _copiar_grade(grade):
    return {turma_id: dict(slots) for turma_id, slots in grade.items()}


def _montar_aulas_geradas(grade, turma_ids=None):
    turma_ids = set(turma_ids) if turma_ids is not None else None
    aulas_geradas = []
    for turma_id, slots in grade.items():
        if turma_ids is not None and turma_id not in turma_ids:
            continue
        for (dia, periodo), aula in slots.items():
            aulas_geradas.append({
                'turma_id': turma_id,
                'professor_id': aula['professor_id'],
                'disciplina_id': aula['disciplina_id'],
                'dia': dia,
                'periodo': periodo,
            })
    return aulas_geradas


def _montar_grade_existente(aulas, turmas, turma_id_ignorada=None):
    turmas_ids = {turma['id'] for turma in turmas}
    grade = {turma_id: {} for turma_id in turmas_ids}

    for aula in aulas:
        turma_id = aula['turma_id']
        if turma_id == turma_id_ignorada or turma_id not in turmas_ids:
            continue

        grade[turma_id][(aula['dia'], aula['periodo'])] = {
            'professor_id': aula['professor_id'],
            'disciplina_id': aula['disciplina_id'],
        }

    return grade


def _gerar_grade_por_demandas(demandas, turmas, semente, grade_base=None):
    rng = random.Random(semente)
    grade = _copiar_grade(grade_base) if grade_base is not None else {t['id']: {} for t in turmas}
    pendencias = []
    turmas_por_id = {turma['id']: turma for turma in turmas}

    for demanda in _ordenar_demandas(demandas, turmas, rng):
        colocadas = _alocar_demanda(
            grade,
            turmas_por_id[demanda['turma_id']],
            demanda['disciplina'],
            demanda['qtd'],
            [demanda['professor']],
            5000,
            rng,
        )
        if colocadas < demanda['qtd']:
            pendencias.append({
                'professor_nome': demanda['professor']['nome'],
                'turma_id': demanda['turma_id'],
                'disciplina_nome': demanda['disciplina']['nome'],
                'faltantes': demanda['qtd'] - colocadas,
            })

    return grade, pendencias


def _resumir_pendencias(pendencias, turmas):
    turmas_por_id = {turma['id']: turma for turma in turmas}
    partes = []
    for pendencia in pendencias[:5]:
        turma_nome = turmas_por_id.get(pendencia['turma_id'], {}).get('nome', pendencia['turma_id'])
        partes.append(
            f"{turma_nome}/{pendencia['disciplina_nome']}/{pendencia['professor_nome']}: "
            f"{pendencia['faltantes']}"
        )
    if len(pendencias) > 5:
        partes.append(f"mais {len(pendencias) - 5} pendência(s)")
    return '; '.join(partes)


def gerar_horario(escola_id, turma_id_especifica=None):
    """
    Gera automaticamente a grade de horários para uma escola ou turma específica.
    Retorna (sucesso: bool, mensagem: str, total_aulas: int)
    """
    professores = listar_professores(escola_id)
    todas_turmas = listar_turmas(escola_id)
    disciplinas = listar_disciplinas(escola_id)
    aulas_existentes = listar_aulas(escola_id) if turma_id_especifica else []

    if turma_id_especifica:
        turmas = [t for t in todas_turmas if t['id'] == turma_id_especifica]
    else:
        turmas = todas_turmas

    if not professores:
        return False, "Cadastre pelo menos um professor antes de gerar o horário.", 0
    if not turmas:
        return False, "Cadastre pelo menos uma turma antes de gerar o horário.", 0
    if not disciplinas:
        return False, "Cadastre pelo menos uma disciplina antes de gerar o horário.", 0

    grade_base = (
        _montar_grade_existente(aulas_existentes, todas_turmas, turma_id_especifica)
        if turma_id_especifica
        else None
    )
    grade = _copiar_grade(grade_base) if grade_base is not None else {t['id']: {} for t in turmas}
    n_disc = len(disciplinas)

    tentativas_max = 5000
    demandas = _demandas_detalhadas(professores, turmas, disciplinas)

    if demandas:
        erros_capacidade = _validar_capacidade_demandas(demandas, turmas)
        if erros_capacidade:
            return (
                False,
                "Não foi possível gerar uma grade completa. Ajuste as cargas: "
                + '; '.join(erros_capacidade),
                0,
            )

        total_esperado = sum(demanda['qtd'] for demanda in demandas)
        melhor_grade = None
        melhores_pendencias = []
        melhor_total = -1

        semente_base = _nova_semente_aleatoria()
        for tentativa in range(MAX_TENTATIVAS_GRADE):
            grade_tentativa, pendencias = _gerar_grade_por_demandas(
                demandas,
                turmas,
                semente_base + tentativa,
                grade_base,
            )
            total_tentativa = sum(len(grade_tentativa.get(turma['id'], {})) for turma in turmas)
            if total_tentativa > melhor_total:
                melhor_grade = grade_tentativa
                melhores_pendencias = pendencias
                melhor_total = total_tentativa
            if total_tentativa == total_esperado:
                break

        if melhor_total < total_esperado:
            return (
                False,
                "Não foi possível gerar uma grade completa. "
                f"Melhor tentativa: {melhor_total} de {total_esperado} aulas. "
                f"Pendências: {_resumir_pendencias(melhores_pendencias, turmas)}.",
                0,
            )

        grade = melhor_grade
    else:
        rng = random.Random(_nova_semente_aleatoria())
        for turma in turmas:
            turma_id = turma['id']
            aulas_por_disc = max(1, (len(DIAS) * len(_periodos_turma(turma))) // n_disc)
            discs_shuffled = disciplinas.copy()
            rng.shuffle(discs_shuffled)

            for disc in discs_shuffled:
                disc_id = disc['id']
                profs_disponiveis = [
                    p for p in professores
                    if disc_id in p.get('disciplina_ids', []) and turma_id in p.get('turma_ids', [])
                ]
                if not profs_disponiveis:
                    continue

                _alocar_demanda(
                    grade,
                    turma,
                    disc,
                    aulas_por_disc,
                    profs_disponiveis,
                    tentativas_max,
                    rng,
                )

    aulas_geradas = _montar_aulas_geradas(grade, [turma['id'] for turma in turmas])

    if not aulas_geradas:
        return False, "Não foi possível gerar nenhuma aula. Verifique os vínculos entre professores, turmas e disciplinas.", 0

    salvar_aulas(escola_id, aulas_geradas, turma_id_especifica)
    return True, f"Horário gerado com sucesso! {len(aulas_geradas)} aulas distribuídas.", len(aulas_geradas)
