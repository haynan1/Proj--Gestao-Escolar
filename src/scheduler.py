import random
from utils.conflitos import (
    DIAS, PERIODOS,
    verificar_conflito_professor,
    verificar_conflito_turma,
    verificar_aulas_seguidas,
    contar_aulas_professor
)
from models.professor import listar_professores
from models.turma import listar_turmas
from models.disciplina import listar_disciplinas
from models.aula import salvar_aulas


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

    # grade[turma_id][(dia, periodo)] = {professor_id, disciplina_id, ...}
    grade = {t['id']: {} for t in turmas}

    # Calcular quantas aulas por disciplina por turma
    # Distribuição: total de slots / número de disciplinas
    total_slots = len(DIAS) * len(PERIODOS)  # 25 por turma
    n_disc = len(disciplinas)
    aulas_por_disc = max(1, total_slots // n_disc)

    aulas_geradas = []
    tentativas_max = 5000

    for turma in turmas:
        turma_id = turma['id']
        # Embaralha disciplinas para distribuição variada
        discs_shuffled = disciplinas.copy()
        random.shuffle(discs_shuffled)

        for disc in discs_shuffled:
            disc_id = disc['id']
            profs_disponiveis = [
                p for p in professores
                if p['disciplina_id'] == disc_id and turma_id in p.get('turma_ids', [])
            ]
            if not profs_disponiveis:
                continue

            # Quantas aulas desta disciplina nesta turma
            qtd = aulas_por_disc
            colocadas = 0
            tentativas = 0

            # Embaralha dias e períodos
            slots = [(d, p) for d in DIAS for p in PERIODOS]
            random.shuffle(slots)

            for (dia, periodo) in slots:
                if colocadas >= qtd:
                    break
                if tentativas > tentativas_max:
                    break
                tentativas += 1

                # Verifica conflito de turma
                if verificar_conflito_turma(grade, turma_id, dia, periodo):
                    continue

                # Verifica aulas seguidas
                if verificar_aulas_seguidas(grade, turma_id, disc_id, dia, periodo):
                    continue

                # Tenta alocar um professor disponível
                profs_shuffled = profs_disponiveis.copy()
                random.shuffle(profs_shuffled)

                for prof in profs_shuffled:
                    # Verifica dia disponível
                    if dia not in prof['dias_lista']:
                        continue

                    # Verifica conflito de professor
                    if verificar_conflito_professor(grade, prof['id'], dia, periodo):
                        continue

                    # Verifica limite semanal
                    if contar_aulas_professor(grade, prof['id']) >= prof['max_aulas_semana']:
                        continue

                    # Aloca a aula
                    grade[turma_id][(dia, periodo)] = {
                        'professor_id': prof['id'],
                        'disciplina_id': disc_id,
                        'professor_nome': prof['nome'],
                        'disciplina_nome': disc['nome'],
                        'disciplina_cor': disc['cor'],
                    }
                    colocadas += 1
                    break

    # Converte grade para lista de aulas
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
