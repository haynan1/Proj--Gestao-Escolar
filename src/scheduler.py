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
from models.turno import normalizar_turno


MAX_TENTATIVAS_GRADE = 100
MAX_TENTATIVAS_AJUSTE_MINIMO = 300


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
    turmas_por_professor = defaultdict(set)

    for demanda in demandas:
        demanda_por_turma[demanda['turma_id']] += demanda['qtd']
        professor = demanda['professor']
        professores_por_id[professor['id']] = professor
        demanda_por_professor[professor['id']] += demanda['qtd']
        turmas_por_professor[professor['id']].add(demanda['turma_id'])

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

        dias_lista = professor.get('dias_lista', [])
        if dias_lista:
            turmas_ids_prof = turmas_por_professor[professor_id]
            max_periodos = max(
                (len(_periodos_turma(turmas_por_id[t_id])) for t_id in turmas_ids_prof if t_id in turmas_por_id),
                default=5,
            )
            capacidade_dias = len(dias_lista) * max_periodos
            if demanda_total > capacidade_dias:
                nomes_dias = ', '.join(dias_lista)
                erros.append(
                    f"{professor['nome']}: {demanda_total} aulas configuradas, mas disponível em apenas "
                    f"{len(dias_lista)} dia(s) ({nomes_dias}) — máximo {capacidade_dias} aulas possíveis. "
                    f"Reduza as cargas ou reative o dia."
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


def _slot_bloqueado(slots_bloqueados, turma_id, dia, periodo):
    if not slots_bloqueados:
        return False
    return (
        (turma_id, dia, periodo) in slots_bloqueados
        or (None, dia, periodo) in slots_bloqueados
    )


def _alocar_demanda(
    grade,
    turma,
    disc,
    qtd,
    professores_disponiveis,
    tentativas_max,
    rng,
    slots_bloqueados=None,
    ignorar_dias=False,
):
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

        if _slot_bloqueado(slots_bloqueados, turma_id, dia, periodo):
            continue

        if verificar_conflito_turma(grade, turma_id, dia, periodo):
            continue

        if verificar_aulas_seguidas(grade, turma_id, disc_id, dia, periodo, max(periodos)):
            continue

        profs_shuffled = professores_disponiveis.copy()
        rng.shuffle(profs_shuffled)

        for prof in profs_shuffled:
            if not ignorar_dias and dia not in prof['dias_lista']:
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


def _gerar_grade_por_demandas(
    demandas,
    turmas,
    semente,
    grade_base=None,
    slots_bloqueados=None,
    ignorar_dias=False,
):
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
            slots_bloqueados,
            ignorar_dias=ignorar_dias,
        )
        if colocadas < demanda['qtd']:
            pendencias.append({
                'professor_id': demanda['professor']['id'],
                'professor_nome': demanda['professor']['nome'],
                'turma_id': demanda['turma_id'],
                'disciplina_nome': demanda['disciplina']['nome'],
                'faltantes': demanda['qtd'] - colocadas,
            })

    return grade, pendencias


def _professores_com_dias_estendidos(professores, professor_ids_pendentes):
    """
    Retorna cópia da lista de professores onde os professores com pendências
    têm seus dias disponíveis estendidos para toda a semana.
    Os dias originais ficam em '_dias_originais' para rastreamento posterior.
    """
    resultado = []
    for prof in professores:
        if prof['id'] in professor_ids_pendentes and set(prof['dias_lista']) != set(DIAS):
            prof_novo = dict(prof)
            prof_novo['_dias_originais'] = prof['dias_lista']
            prof_novo['dias_lista'] = list(DIAS)
            resultado.append(prof_novo)
        else:
            resultado.append(prof)
    return resultado


def _extrair_ajustes(grade, professores_por_id):
    """
    Varre a grade e identifica quais aulas usaram professores em dias
    fora da sua disponibilidade original. Retorna lista de ajustes.
    """
    ajustes = []
    vistos = set()
    for turma_id, slots in grade.items():
        for (dia, periodo), aula in slots.items():
            if not aula:
                continue
            prof_id = aula.get('professor_id')
            prof = professores_por_id.get(prof_id)
            if not prof or '_dias_originais' not in prof:
                continue
            if dia not in prof['_dias_originais']:
                chave = (prof_id, dia)
                if chave not in vistos:
                    vistos.add(chave)
                    ajustes.append({
                        'professor_id': prof_id,
                        'professor_nome': prof['nome'],
                        'dia': dia,
                        'dias_originais': list(prof['_dias_originais']),
                    })
    return sorted(ajustes, key=lambda a: (a['professor_nome'], a['dia']))


def _contar_aulas_ajustadas(grade, professores_por_id):
    total = 0
    for slots in grade.values():
        for (dia, _periodo), aula in slots.items():
            if not aula:
                continue
            prof = professores_por_id.get(aula.get('professor_id'))
            if prof and '_dias_originais' in prof and dia not in prof['_dias_originais']:
                total += 1
    return total


def _buscar_grade_com_menor_ajuste(
    professores,
    turmas,
    disciplinas,
    grade_base,
    slots_bloqueados,
    slots_base,
    professor_ids_relaxados,
    completar_apenas=False,
):
    """
    Procura uma grade completa relaxando apenas disponibilidade de dias e escolhe
    a tentativa que usa menos aulas fora dos dias cadastrados.
    """
    professores_alt = _professores_com_dias_estendidos(professores, professor_ids_relaxados)
    professores_por_id_alt = {p['id']: p for p in professores_alt}
    demandas_alt = _demandas_detalhadas(professores_alt, turmas, disciplinas)
    demandas_alt_para_gerar = (
        _ajustar_demandas_grade_existente(demandas_alt, grade_base)
        if (completar_apenas and grade_base is not None)
        else demandas_alt
    )
    total_esperado = sum(demanda['qtd'] for demanda in demandas_alt_para_gerar)
    melhor_grade = None
    melhores_pendencias = []
    melhor_total = -1
    melhor_ajustes = []
    melhor_score = None
    semente_base = _nova_semente_aleatoria()

    for tentativa in range(MAX_TENTATIVAS_AJUSTE_MINIMO):
        grade_tentativa, pendencias = _gerar_grade_por_demandas(
            demandas_alt_para_gerar,
            turmas,
            semente_base + tentativa,
            grade_base,
            slots_bloqueados,
        )
        total_tentativa = sum(len(grade_tentativa.get(t['id'], {})) for t in turmas) - slots_base
        if total_tentativa > melhor_total:
            melhor_grade = grade_tentativa
            melhores_pendencias = pendencias
            melhor_total = total_tentativa

        if total_tentativa < total_esperado:
            continue

        ajustes = _extrair_ajustes(grade_tentativa, professores_por_id_alt)
        score = (
            _contar_aulas_ajustadas(grade_tentativa, professores_por_id_alt),
            len(ajustes),
        )
        if melhor_score is None or score < melhor_score:
            melhor_grade = grade_tentativa
            melhores_pendencias = []
            melhor_total = total_tentativa
            melhor_ajustes = ajustes
            melhor_score = score
            if score == (0, 0):
                break

    return (
        melhor_grade,
        melhores_pendencias,
        melhor_total,
        total_esperado,
        melhor_ajustes if melhor_score is not None else None,
    )


def _ajustar_demandas_grade_existente(demandas, grade):
    """Subtrai aulas já posicionadas no grade das demandas — para modo completar."""
    resultado = []
    for demanda in demandas:
        turma_id = demanda['turma_id']
        professor_id = demanda['professor']['id']
        disciplina_id = demanda['disciplina']['id']
        ja_colocadas = sum(
            1
            for aula in (grade.get(turma_id) or {}).values()
            if aula
            and aula.get('professor_id') == professor_id
            and aula.get('disciplina_id') == disciplina_id
        )
        qtd_restante = demanda['qtd'] - ja_colocadas
        if qtd_restante > 0:
            resultado.append({**demanda, 'qtd': qtd_restante})
    return resultado


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


def _enriquecer_pendencias(pendencias, turmas):
    turmas_por_id = {turma['id']: turma for turma in turmas}
    return [
        {**p, 'turma_nome': turmas_por_id.get(p['turma_id'], {}).get('nome', str(p['turma_id']))}
        for p in pendencias
    ]


def _tentar_gerar(
    professores,
    turmas,
    disciplinas,
    demandas_para_gerar,
    grade_base,
    slots_bloqueados,
    slots_base,
    ignorar_dias=False,
):
    """Executa as MAX_TENTATIVAS_GRADE tentativas e devolve a melhor grade encontrada."""
    total_esperado = sum(demanda['qtd'] for demanda in demandas_para_gerar)
    melhor_grade = None
    melhores_pendencias = []
    melhor_total = -1
    semente_base = _nova_semente_aleatoria()
    for tentativa in range(MAX_TENTATIVAS_GRADE):
        grade_tentativa, pendencias = _gerar_grade_por_demandas(
            demandas_para_gerar,
            turmas,
            semente_base + tentativa,
            grade_base,
            slots_bloqueados,
            ignorar_dias=ignorar_dias,
        )
        total_tentativa = sum(len(grade_tentativa.get(t['id'], {})) for t in turmas) - slots_base
        if total_tentativa > melhor_total:
            melhor_grade = grade_tentativa
            melhores_pendencias = pendencias
            melhor_total = total_tentativa
        if total_tentativa >= total_esperado:
            break
    return melhor_grade, melhores_pendencias, melhor_total, total_esperado


def montar_horario_gerado(
    escola_id,
    turma_id_especifica=None,
    turno=None,
    professor_ids_excluidos=None,
    slots_bloqueados=None,
    permitir_grade_incompleta=False,
    completar_apenas=False,
    ajuste_minimo=False,
):
    """
    Monta automaticamente a grade de horários para uma escola ou turma específica.
    Retorna (sucesso: bool, mensagem: str, aulas_geradas: list[dict])
    ou, em falha com pendências: (False, msg, [], pendencias, melhor_total, total_esperado)
    ou, com ajuste_minimo bem-sucedido: (True, msg, aulas, ajustes)

    completar_apenas: preserva aulas manuais existentes e preenche apenas os slots vazios.
    ajuste_minimo: quando a geração normal falha, tenta relaxar dias apenas dos professores
                   bloqueantes (mínimo de ajuste), reportando exatamente o que mudou.
    """
    turno = normalizar_turno(turno)
    professores = listar_professores(escola_id, turno)
    professor_ids_excluidos = {int(pid) for pid in (professor_ids_excluidos or []) if pid}
    if professor_ids_excluidos:
        professores = [p for p in professores if p['id'] not in professor_ids_excluidos]
    todas_turmas = listar_turmas(escola_id, turno)
    disciplinas = listar_disciplinas(escola_id, turno)
    aulas_existentes = listar_aulas(escola_id, turno) if turma_id_especifica else []

    if turma_id_especifica:
        turmas = [t for t in todas_turmas if t['id'] == turma_id_especifica]
    else:
        turmas = todas_turmas

    if not professores:
        return False, "Cadastre pelo menos um professor antes de gerar o horário.", []
    if not turmas:
        return False, "Cadastre pelo menos uma turma antes de gerar o horário.", []
    if not disciplinas:
        return False, "Cadastre pelo menos uma disciplina antes de gerar o horário.", []

    if completar_apenas and turma_id_especifica:
        grade_base = _montar_grade_existente(aulas_existentes, todas_turmas, None)
    else:
        grade_base = (
            _montar_grade_existente(aulas_existentes, todas_turmas, turma_id_especifica)
            if turma_id_especifica else None
        )

    slots_base = sum(len((grade_base or {}).get(t['id'], {})) for t in turmas)
    n_disc = len(disciplinas)
    demandas = _demandas_detalhadas(professores, turmas, disciplinas)

    if demandas:
        if not (completar_apenas or permitir_grade_incompleta or ajuste_minimo):
            erros_capacidade = _validar_capacidade_demandas(demandas, turmas)
            if erros_capacidade:
                return (
                    False,
                    "Não foi possível gerar uma grade completa. Ajuste as cargas: "
                    + '; '.join(erros_capacidade),
                    [],
                )

        demandas_para_gerar = (
            _ajustar_demandas_grade_existente(demandas, grade_base)
            if (completar_apenas and grade_base is not None)
            else demandas
        )

        melhor_grade, melhores_pendencias, melhor_total, total_esperado = _tentar_gerar(
            professores, turmas, disciplinas, demandas_para_gerar, grade_base, slots_bloqueados, slots_base,
        )

        if melhor_total < total_esperado:
            if ajuste_minimo and melhores_pendencias:
                professor_ids_pendentes = {p['professor_id'] for p in melhores_pendencias if p.get('professor_id')}
                melhor_grade_ajuste, pend_ajuste, total_ajuste, total_esp_ajuste, ajustes = (
                    _buscar_grade_com_menor_ajuste(
                        professores,
                        turmas,
                        disciplinas,
                        grade_base,
                        slots_bloqueados,
                        slots_base,
                        professor_ids_pendentes,
                        completar_apenas=completar_apenas,
                    )
                )

                if total_ajuste < total_esp_ajuste:
                    professor_ids_todos = {p['id'] for p in professores}
                    melhor_grade_ajuste, pend_ajuste, total_ajuste, total_esp_ajuste, ajustes = (
                        _buscar_grade_com_menor_ajuste(
                            professores,
                            turmas,
                            disciplinas,
                            grade_base,
                            slots_bloqueados,
                            slots_base,
                            professor_ids_todos,
                            completar_apenas=completar_apenas,
                        )
                    )

                if total_ajuste >= total_esp_ajuste:
                    ajustes = ajustes or []
                    aulas_geradas = _montar_aulas_geradas(melhor_grade_ajuste, [t['id'] for t in turmas])
                    if completar_apenas:
                        novas = len(aulas_geradas) - slots_base
                        msg = f"Horário completado com a menor correção encontrada! {novas} aula(s) adicionada(s)."
                    else:
                        msg = f"Horário gerado com a menor correção encontrada! {len(aulas_geradas)} aulas distribuídas."
                    salvar_aulas(escola_id, aulas_geradas, turma_id_especifica, turno)
                    return True, msg, aulas_geradas, ajustes

                return (
                    False,
                    "Não foi possível fechar a grade sem alterar limites estruturais. "
                    "Verifique as cargas e vínculos dos professores.",
                    [],
                    _enriquecer_pendencias(pend_ajuste or melhores_pendencias, turmas),
                    max(melhor_total, total_ajuste),
                    total_esperado,
                )

            if not (completar_apenas or permitir_grade_incompleta):
                return (
                    False,
                    "Não foi possível gerar uma grade completa. "
                    f"Melhor tentativa: {melhor_total} de {total_esperado} aulas. "
                    f"Pendências: {_resumir_pendencias(melhores_pendencias, turmas)}.",
                    [],
                    _enriquecer_pendencias(melhores_pendencias, turmas),
                    melhor_total,
                    total_esperado,
                )

        grade = melhor_grade
    else:
        rng = random.Random(_nova_semente_aleatoria())
        grade = _copiar_grade(grade_base) if grade_base is not None else {t['id']: {} for t in turmas}
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
                _alocar_demanda(grade, turma, disc, aulas_por_disc, profs_disponiveis, 5000, rng, slots_bloqueados)

    aulas_geradas = _montar_aulas_geradas(grade, [t['id'] for t in turmas])
    if not aulas_geradas:
        return False, "Não foi possível gerar nenhuma aula. Verifique os vínculos entre professores, turmas e disciplinas.", []

    if completar_apenas:
        novas = len(aulas_geradas) - slots_base
        if novas == 0:
            return True, "O horário desta turma já estava completo. Nenhuma aula foi adicionada.", aulas_geradas
        return True, f"Horário completado! {novas} aula(s) adicionada(s) aos espaços vazios.", aulas_geradas

    return True, f"Horário gerado com sucesso! {len(aulas_geradas)} aulas distribuídas.", aulas_geradas


def gerar_horario(escola_id, turma_id_especifica=None, turno=None, completar_apenas=False, ajuste_minimo=False):
    """
    Gera automaticamente a grade de horários para uma escola ou turma específica.
    Retorna (sucesso: bool, mensagem: str, total_aulas: int, erros: dict|None, ajustes: list|None)
    erros = {'pendencias': list, 'melhor_total': int, 'total_esperado': int} quando grade incompleta.
    ajustes = lista de {'professor_nome', 'dia', 'dias_originais'} quando ajuste_minimo foi aplicado.

    completar_apenas: preserva aulas manuais e preenche apenas slots vazios (exige turma_id_especifica).
    ajuste_minimo: quando a geração normal falha, tenta com o mínimo de relaxamento de regras de dias.
    """
    result = montar_horario_gerado(
        escola_id,
        turma_id_especifica,
        turno,
        completar_apenas=completar_apenas,
        ajuste_minimo=ajuste_minimo,
    )
    sucesso, mensagem, aulas_geradas = result[0], result[1], result[2]

    if not sucesso:
        erros = (
            {'pendencias': result[3], 'melhor_total': result[4], 'total_esperado': result[5]}
            if len(result) > 3
            else None
        )
        return False, mensagem, 0, erros, None

    # ajuste_minimo bem-sucedido vem com resultado[3] = lista de ajustes
    ajustes = result[3] if len(result) > 3 else None

    # salvar_aulas já foi chamado dentro de montar_horario_gerado no caminho ajuste_minimo;
    # nos outros caminhos, salva aqui.
    if ajustes is None:
        salvar_aulas(escola_id, aulas_geradas, turma_id_especifica, turno)

    return True, mensagem, len(aulas_geradas), None, ajustes
