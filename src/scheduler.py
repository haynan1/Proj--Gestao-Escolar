import random
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
from models.aula import salvar_aulas


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

    random.shuffle(demandas)
    return demandas


def _periodos_turma(turma):
    aulas_por_dia = int(turma.get('aulas_por_dia') or 5)
    return list(range(1, aulas_por_dia + 1))


def _alocar_demanda(grade, turma, disc, qtd, professores_disponiveis, tentativas_max):
    turma_id = turma['id']
    periodos = _periodos_turma(turma)
    disc_id = disc['id']
    colocadas = 0
    tentativas = 0

    slots = [(d, p) for d in DIAS for p in periodos]
    random.shuffle(slots)

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
        random.shuffle(profs_shuffled)

        for prof in profs_shuffled:
            if dia not in prof['dias_lista']:
                continue

            if verificar_conflito_professor(grade, prof['id'], dia, periodo):
                continue

            if contar_aulas_professor(grade, prof['id']) >= prof['max_aulas_semana']:
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


def gerar_horario(escola_id, turma_id_especifica=None):
    """
    Gera automaticamente a grade de horários para uma escola ou turma específica.
    Retorna (sucesso: bool, mensagem: str, total_aulas: int)
    """
    professores = listar_professores(escola_id)
    todas_turmas = listar_turmas(escola_id)
    disciplinas = listar_disciplinas(escola_id)

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

    grade = {t['id']: {} for t in turmas}
    n_disc = len(disciplinas)

    aulas_geradas = []
    tentativas_max = 5000
    demandas = _demandas_detalhadas(professores, turmas, disciplinas)
    turmas_por_id = {turma['id']: turma for turma in turmas}

    if demandas:
        for demanda in demandas:
            _alocar_demanda(
                grade,
                turmas_por_id[demanda['turma_id']],
                demanda['disciplina'],
                demanda['qtd'],
                [demanda['professor']],
                tentativas_max,
            )
    else:
        for turma in turmas:
            turma_id = turma['id']
            aulas_por_disc = max(1, (len(DIAS) * len(_periodos_turma(turma))) // n_disc)
            discs_shuffled = disciplinas.copy()
            random.shuffle(discs_shuffled)

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
                )

    for turma_id, slots in grade.items():
        for (dia, periodo), aula in slots.items():
            aulas_geradas.append({
                'turma_id': turma_id,
                'professor_id': aula['professor_id'],
                'disciplina_id': aula['disciplina_id'],
                'dia': dia,
                'periodo': periodo,
            })

    if not aulas_geradas:
        return False, "Não foi possível gerar nenhuma aula. Verifique os vínculos entre professores, turmas e disciplinas.", 0

    salvar_aulas(escola_id, aulas_geradas, turma_id_especifica)
    return True, f"Horário gerado com sucesso! {len(aulas_geradas)} aulas distribuídas.", len(aulas_geradas)
