DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']
PERIODOS = [1, 2, 3, 4, 5]


def verificar_conflito_professor(grade, professor_id, dia, periodo):
    """Verifica se o professor já tem aula neste dia/período."""
    for turma_id, slots in grade.items():
        aula = slots.get((dia, periodo))
        if aula and aula['professor_id'] == professor_id:
            return True
    return False


def verificar_conflito_turma(grade, turma_id, dia, periodo):
    """Verifica se a turma já tem aula neste dia/período."""
    return (dia, periodo) in grade.get(turma_id, {})


def verificar_aulas_seguidas(grade, turma_id, disciplina_id, dia, periodo):
    """Verifica se haveria mais de 2 aulas seguidas da mesma disciplina."""
    slots = grade.get(turma_id, {})
    count = 0
    # Verifica períodos anteriores
    for p in range(max(1, periodo - 2), periodo):
        aula = slots.get((dia, p))
        if aula and aula['disciplina_id'] == disciplina_id:
            count += 1
    # Verifica períodos posteriores
    for p in range(periodo + 1, min(6, periodo + 3)):
        aula = slots.get((dia, p))
        if aula and aula['disciplina_id'] == disciplina_id:
            count += 1
    return count >= 2


def contar_aulas_professor(grade, professor_id):
    """Conta quantas aulas o professor já tem na grade."""
    total = 0
    for turma_id, slots in grade.items():
        for aula in slots.values():
            if aula['professor_id'] == professor_id:
                total += 1
    return total
