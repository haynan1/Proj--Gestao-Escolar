import os
from datetime import date, datetime, timedelta

from flask import (
    Blueprint,
    after_this_request,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from access_control import forbid_without_school_permission, user_has_permission
from auth import login_required
from exports.excel_export import exportar_excel
from exports.pdf_export import exportar_pdf, exportar_pdf_matriz, exportar_relatorio_mensal_pdf
from models.aula import (
    ScheduleConflictError,
    ScheduleValidationError,
    criar_aula_manual,
    deletar_aula,
    limpar_aulas,
    listar_aulas,
    mover_aula,
)
from models.disciplina import (
    COR_DISCIPLINA_PADRAO,
    DisciplineInUseError,
    atualizar_disciplina,
    criar_disciplina,
    deletar_disciplina,
    listar_disciplinas,
)
from models.escola import buscar_escola, definir_horario_turno_travado, horario_turno_travado
from models.horario_temporario import (
    HorarioTemporarioValidationError,
    criar_horarios_temporarios_lote,
    criar_horario_temporario,
    deletar_horarios_temporarios_grupo,
    deletar_horario_temporario,
    listar_grupos_horarios_temporarios,
    listar_horarios_temporarios,
)
from models.professor import (
    CORES_PROFESSOR,
    COR_PROFESSOR_PADRAO,
    atualizar_professor,
    criar_professor,
    deletar_professor,
    listar_professores,
)
from models.prontuario import (
    PRIORIDADES_PRONTUARIO,
    STATUS_PRONTUARIO,
    ProntuarioValidationError,
    arquivar_prontuario,
    criar_prontuario,
    listar_prontuarios,
    registrar_feedback_prontuario,
)
from models.relatorio_professor import (
    TIPOS_OCORRENCIA,
    RelatorioProfessorValidationError,
    criar_relatorio_professor,
    deletar_relatorio_professor,
    listar_relatorios_professores,
)
from models.turma import atualizar_turma, criar_turma, deletar_turma, listar_turmas
from models.turno import TURNOS, normalizar_turno
from scheduler import gerar_horario, montar_horario_gerado
from utils.conflitos import PERIODOS


dashboard_bp = Blueprint('dashboard', __name__)

DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']


def _build_horario_balance(turmas, professores):
    cargas_por_turma = {turma['id']: 0 for turma in turmas}

    for professor in professores:
        for carga in professor.get('cargas_lista', []):
            turma_id = carga.get('turma_id')
            if turma_id in cargas_por_turma:
                cargas_por_turma[turma_id] += int(carga.get('aulas_semana') or 0)

    turmas_balance = []
    total_permitido = 0
    total_cadastrado = 0

    for turma in turmas:
        aulas_por_dia = int(turma.get('aulas_por_dia') or 5)
        permitido = aulas_por_dia * len(DIAS_SEMANA)
        cadastrado = cargas_por_turma.get(turma['id'], 0)
        diferenca = cadastrado - permitido

        if diferenca == 0:
            status = 'ok'
            status_label = 'Completo'
        elif diferenca > 0:
            status = 'over'
            status_label = f'Excede {diferenca}'
        else:
            status = 'under'
            status_label = f'Faltam {abs(diferenca)}'

        total_permitido += permitido
        total_cadastrado += cadastrado
        turmas_balance.append({
            'id': turma['id'],
            'nome': turma['nome'],
            'aulas_por_dia': aulas_por_dia,
            'permitido': permitido,
            'cadastrado': cadastrado,
            'diferenca': diferenca,
            'status': status,
            'status_label': status_label,
        })

    total_diferenca = total_cadastrado - total_permitido
    if total_diferenca == 0:
        total_status = 'ok'
        total_status_label = 'Fechado'
    elif total_diferenca > 0:
        total_status = 'over'
        total_status_label = f'Excede {total_diferenca}'
    else:
        total_status = 'under'
        total_status_label = f'Faltam {abs(total_diferenca)}'

    return {
        'total_permitido': total_permitido,
        'total_cadastrado': total_cadastrado,
        'total_diferenca': total_diferenca,
        'total_status': total_status,
        'total_status_label': total_status_label,
        'turmas': turmas_balance,
    }


def _build_ai_audit_text(escola, turno_id, turno_label, horario_balance, professores):
    linhas = [
        f'RELATÓRIO ESPECÍFICO DO TURNO: {turno_label} ({turno_id})',
        '',
        'Analise os dados abaixo e indique onde estão os erros de carga horária.',
        'Estes dados são exclusivos deste turno. Ignore manhã, tarde ou noite se não forem o turno indicado acima.',
        'Compare o dashboard de erros das turmas com as aulas cadastradas por professor.',
        'Ao avaliar nomes parecidos de matérias, considere sempre o conjunto Turma + Matéria.',
        'Não aponte duplicidade apenas por diferença de maiúsculas/minúsculas quando as matérias estiverem em turmas diferentes.',
        '',
        f"Escola: {escola.get('nome') or '-'}",
        f'Turno: {turno_label}',
        '',
        'Resumo geral da carga horária:',
        f"- Horários permitidos: {horario_balance['total_permitido']}",
        f"- Aulas cadastradas: {horario_balance['total_cadastrado']}",
        f"- Diferença: {horario_balance['total_diferenca']}",
        f"- Status: {horario_balance['total_status_label']}",
        '',
        'Dashboard de erros por turma:',
    ]

    if horario_balance.get('turmas'):
        for turma in horario_balance['turmas']:
            linhas.append(
                f"- {turma['nome']}: permitidos {turma['permitido']}, "
                f"cadastrados {turma['cadastrado']}, diferença {turma['diferenca']}, "
                f"status {turma['status_label']}"
            )
    else:
        linhas.append('- Nenhuma turma cadastrada.')

    linhas.extend([
        '',
        'Cargas cadastradas por professor:',
        'Formato: Professor | Turma | Matéria | Aulas por semana',
    ])

    if professores:
        for professor in professores:
            cargas = professor.get('cargas_lista') or []
            if cargas:
                for carga in cargas:
                    linhas.append(
                        f"- {professor.get('nome') or '-'} | "
                        f"{carga.get('turma_nome') or '-'} | "
                        f"{carga.get('disciplina_nome') or '-'} | "
                        f"{int(carga.get('aulas_semana') or 0)}"
                    )
            else:
                linhas.append(f"- {professor.get('nome') or '-'} | - | - | Sem aulas detalhadas cadastradas")
    else:
        linhas.append('- Nenhum professor cadastrado.')

    return '\n'.join(linhas)


def _json_error(message, status_code=400, code='bad_request'):
    response = jsonify({
        'status': 'erro',
        'error': {
            'code': code,
            'message': message,
        },
    })
    response.status_code = status_code
    return response


def _send_temp_file(filepath, download_name):
    @after_this_request
    def remover_temporario(response):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass
        return response

    return send_file(filepath, as_attachment=True, download_name=download_name)


def _parse_cargas_professor(form):
    cargas = []
    prefixo = 'aulas_carga_'
    for nome_campo, valor in form.items():
        if not nome_campo.startswith(prefixo):
            continue

        partes = nome_campo[len(prefixo):].split('_')
        if len(partes) != 2:
            continue

        try:
            aulas_semana = int(valor or 0)
            turma_id = int(partes[0])
            disciplina_id = int(partes[1])
        except ValueError:
            continue

        if aulas_semana > 0:
            cargas.append({
                'turma_id': turma_id,
                'disciplina_id': disciplina_id,
                'aulas_semana': aulas_semana,
            })

    return cargas


def _calcular_max_aulas_professor(cargas, fallback=10):
    total = sum(int(carga.get('aulas_semana') or 0) for carga in cargas)
    return total if total > 0 else fallback


def _build_manual_options(turmas, professores, aulas):
    aulas_por_chave = {}
    for aula in aulas:
        chave = (aula['turma_id'], aula['professor_id'], aula['disciplina_id'])
        aulas_por_chave[chave] = aulas_por_chave.get(chave, 0) + 1

    opcoes = {str(turma['id']): [] for turma in turmas}
    for professor in professores:
        for carga in professor.get('cargas_lista', []):
            total = int(carga.get('aulas_semana') or 0)
            chave = (carga['turma_id'], professor['id'], carga['disciplina_id'])
            usadas = aulas_por_chave.get(chave, 0)
            faltam = max(0, total - usadas)
            if faltam <= 0:
                continue

            opcoes.setdefault(str(carga['turma_id']), []).append({
                'professor_id': professor['id'],
                'professor_nome': professor['nome'],
                'disciplina_id': carga['disciplina_id'],
                'disciplina_nome': carga['disciplina_nome'],
                'disciplina_cor': carga.get('disciplina_cor') or '',
                'faltam': faltam,
                'total': total,
                'dias': professor.get('dias_lista', []),
            })

    for turma_opcoes in opcoes.values():
        turma_opcoes.sort(key=lambda item: (item['disciplina_nome'], item['professor_nome']))
    return opcoes


def _professor_ministra_na_turma(professor, turma_id):
    try:
        turma_id = int(turma_id)
    except (TypeError, ValueError):
        return False

    return any(
        int(carga.get('turma_id') or 0) == turma_id
        and int(carga.get('aulas_semana') or 0) > 0
        for carga in professor.get('cargas_lista', [])
    )


def _build_alternative_manual_options(professores_por_turno):
    opcoes = {}
    for turno_id, professores_turno in professores_por_turno.items():
        itens = []
        for professor in professores_turno:
            dias = professor.get('dias_lista') or []
            for carga in professor.get('cargas_lista', []):
                if int(carga.get('aulas_semana') or 0) <= 0:
                    continue
                itens.append({
                    'professor_id': professor['id'],
                    'professor_nome': professor['nome'],
                    'disciplina_id': carga['disciplina_id'],
                    'disciplina_nome': carga['disciplina_nome'],
                    'turma_id': carga['turma_id'],
                    'turma_nome': carga.get('turma_nome') or '',
                    'dias': dias,
                })
        itens.sort(key=lambda item: (item['turma_nome'], item['professor_nome'], item['disciplina_nome']))
        opcoes[turno_id] = itens
    return opcoes


def _build_alternative_occupied_slots(aulas_por_turno):
    ocupados = {}
    for turno_id, aulas_turno in aulas_por_turno.items():
        ocupados[turno_id] = [
            {
                'professor_id': aula.get('professor_id'),
                'turma_id': aula.get('turma_id'),
                'turma_nome': aula.get('turma_nome') or '',
                'dia': aula.get('dia'),
                'periodo': aula.get('periodo'),
            }
            for aula in aulas_turno
            if aula.get('professor_id') and aula.get('dia') and aula.get('periodo')
        ]
    return ocupados


def _build_alternative_official_lessons(aulas_por_turno):
    aulas_oficiais = {}
    for turno_id, aulas_turno in aulas_por_turno.items():
        aulas_oficiais[turno_id] = [
            {
                'turma_id': aula.get('turma_id'),
                'turma_nome': aula.get('turma_nome') or '',
                'professor_id': aula.get('professor_id'),
                'professor_nome': aula.get('professor_nome') or '',
                'disciplina_id': aula.get('disciplina_id'),
                'disciplina_nome': aula.get('disciplina_nome') or '',
                'dia': aula.get('dia'),
                'periodo': aula.get('periodo'),
            }
            for aula in aulas_turno
            if aula.get('turma_id') and aula.get('dia') and aula.get('periodo')
        ]
    return aulas_oficiais


def _build_relatorios_summary(relatorios, professores):
    faltas = [item for item in relatorios if item.get('tipo') == 'falta']
    ocorrencias = [item for item in relatorios if item.get('tipo') == 'ocorrencia']
    por_professor = []

    professores_por_id = {professor['id']: professor for professor in professores}
    grupos = {}
    for item in relatorios:
        chave = item.get('professor_id') or f"snapshot:{item.get('professor_nome') or 'Professor removido'}"
        grupos.setdefault(chave, []).append(item)

    for chave, registros in grupos.items():
        professor_id = registros[0].get('professor_id')
        professor = professores_por_id.get(professor_id)
        por_professor.append({
            'id': professor_id,
            'nome': professor['nome'] if professor else (registros[0].get('professor_nome') or 'Professor removido'),
            'cor': (professor or {}).get('cor') or registros[0].get('professor_cor'),
            'total': len(registros),
            'faltas': len([item for item in registros if item.get('tipo') == 'falta']),
            'ocorrencias': len([item for item in registros if item.get('tipo') == 'ocorrencia']),
        })

    por_professor.sort(key=lambda item: (-item['total'], item['nome']))
    return {
        'total': len(relatorios),
        'faltas': len(faltas),
        'ocorrencias': len(ocorrencias),
        'professores_envolvidos': len(grupos),
        'por_professor': por_professor,
    }


def _load_accessible_escola(escola_id):
    return buscar_escola(escola_id, user=g.user)


def _active_turno():
    return normalizar_turno(request.values.get('turno') or request.args.get('turno'))


def _turno_label(turno_id):
    turno_id = normalizar_turno(turno_id)
    return next((turno['nome'] for turno in TURNOS if turno['id'] == turno_id), 'Matutino')


def _mes_atual():
    return date.today().strftime('%Y-%m')


def _data_atual():
    return date.today().isoformat()


def _parse_date_or_today(value):
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return date.today()


def _is_weekend(value):
    return value.weekday() >= 5


def _date_range_has_weekend(data_inicio, data_fim):
    cursor = data_inicio
    while cursor <= data_fim:
        if _is_weekend(cursor):
            return True
        cursor = cursor + timedelta(days=1)
    return False


def _dias_letivos_no_intervalo(data_inicio, data_fim):
    dias = []
    cursor = data_inicio
    while cursor <= data_fim:
        if cursor.weekday() < len(DIAS_SEMANA):
            dia = DIAS_SEMANA[cursor.weekday()]
            if dia not in dias:
                dias.append(dia)
        cursor = cursor + timedelta(days=1)
    return dias


def _month_label(month_value):
    meses = {
        1: 'Janeiro',
        2: 'Fevereiro',
        3: 'Março',
        4: 'Abril',
        5: 'Maio',
        6: 'Junho',
        7: 'Julho',
        8: 'Agosto',
        9: 'Setembro',
        10: 'Outubro',
        11: 'Novembro',
        12: 'Dezembro',
    }
    try:
        ano, mes = [int(part) for part in str(month_value).split('-', 1)]
        return f'{meses.get(mes, "Mês")} de {ano}'
    except (TypeError, ValueError):
        return 'Mês selecionado'


def _format_date_br(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    try:
        ano, mes, dia = str(value).split('-', 2)
        return f'{dia}/{mes}/{ano}'
    except ValueError:
        return value


def _dashboard_url(endpoint, escola_id, **values):
    values.setdefault('turno', _active_turno())
    return url_for(endpoint, escola_id=escola_id, **values)


def _aula_payload(aula):
    return {
        'turma_id': aula['turma_id'],
        'professor_id': aula['professor_id'],
        'disciplina_id': aula['disciplina_id'],
        'dia': aula['dia'],
        'periodo': aula['periodo'],
    }


def _montar_aulas_alternativas_do_dia(
    escola_id,
    turno,
    dia,
    turma_id=None,
    professor_excluido_id=None,
    periodo_bloqueado=None,
):
    aulas_oficiais = listar_aulas(escola_id, turno)
    if turma_id:
        aulas_oficiais = [aula for aula in aulas_oficiais if aula['turma_id'] == turma_id]

    aulas_dia = [
        _aula_payload(aula)
        for aula in aulas_oficiais
        if aula['dia'] == dia
    ]
    if not aulas_dia:
        return None

    precisa_substituir = set()
    aulas_bloqueadas = []
    for aula in aulas_dia:
        slot = (aula['turma_id'], aula['periodo'])
        if periodo_bloqueado and aula['periodo'] == periodo_bloqueado:
            aulas_bloqueadas.append({
                'turma_id': aula['turma_id'],
                'professor_id': None,
                'disciplina_id': None,
                'dia': aula['dia'],
                'periodo': aula['periodo'],
            })
            continue
        if professor_excluido_id and aula['professor_id'] == professor_excluido_id:
            precisa_substituir.add(slot)
            continue

    if not precisa_substituir:
        return aulas_bloqueadas

    slots_bloqueados = set()
    if periodo_bloqueado:
        if turma_id:
            slots_bloqueados.add((turma_id, dia, periodo_bloqueado))
        else:
            slots_bloqueados.add((None, dia, periodo_bloqueado))

    substitutas = {}
    turmas_para_regerar = [turma_id] if turma_id else sorted({slot[0] for slot in precisa_substituir})
    for turma_regerar_id in turmas_para_regerar:
        sucesso, _, aulas_geradas = montar_horario_gerado(
            escola_id,
            turma_regerar_id,
            turno,
            professor_ids_excluidos=[professor_excluido_id] if professor_excluido_id else None,
            slots_bloqueados=slots_bloqueados,
            permitir_grade_incompleta=True,
        )
        if not sucesso:
            continue
        for aula in aulas_geradas:
            if aula.get('dia') != dia:
                continue
            slot = (aula['turma_id'], aula['periodo'])
            if slot in precisa_substituir and slot not in substitutas:
                substitutas[slot] = aula

    sem_substituta = [
        {
            'turma_id': turma_id_slot,
            'professor_id': None,
            'disciplina_id': None,
            'dia': dia,
            'periodo': periodo,
        }
        for turma_id_slot, periodo in sorted(precisa_substituir)
        if (turma_id_slot, periodo) not in substitutas
    ]

    return aulas_bloqueadas + list(substitutas.values()) + sem_substituta


def _normalizar_aulas_temporarias_para_export(aulas_temporarias):
    aulas = []
    for aula in aulas_temporarias:
        titulo = aula.get('titulo') or 'Horário alternativo'
        aulas.append({
            **aula,
            'disciplina_nome': aula.get('disciplina_nome') or titulo,
            'professor_nome': aula.get('professor_nome') or (aula.get('observacao') or 'Sem professor definido'),
            'disciplina_cor': aula.get('disciplina_cor') or '#eab308',
            'professor_cor': aula.get('professor_cor') or '#eab308',
        })
    return aulas


def _slot_aula(aula):
    try:
        return (int(aula['turma_id']), str(aula['dia']), int(aula['periodo']))
    except (KeyError, TypeError, ValueError):
        return None


def _mesclar_aulas_oficiais_com_alternativas(escola_id, turno, aulas_temporarias):
    aulas_alternativas = _normalizar_aulas_temporarias_para_export(aulas_temporarias)
    turma_ids = {
        int(aula['turma_id'])
        for aula in aulas_alternativas
        if aula.get('turma_id')
    }
    if not turma_ids:
        return [], []

    aulas_oficiais = [
        aula for aula in listar_aulas(escola_id, turno)
        if int(aula.get('turma_id') or 0) in turma_ids
    ]
    alternativas_por_slot = {
        slot: aula
        for aula in aulas_alternativas
        for slot in [_slot_aula(aula)]
        if slot
    }

    aulas_mescladas = []
    slots_usados = set()
    for aula in aulas_oficiais:
        slot = _slot_aula(aula)
        if slot in alternativas_por_slot:
            aulas_mescladas.append(alternativas_por_slot[slot])
            slots_usados.add(slot)
        else:
            aulas_mescladas.append(aula)

    for slot, aula in alternativas_por_slot.items():
        if slot not in slots_usados:
            aulas_mescladas.append(aula)

    turmas = [
        turma for turma in listar_turmas(escola_id, turno)
        if int(turma.get('id') or 0) in turma_ids
    ]
    return aulas_mescladas, turmas


def _filtrar_horarios_temporarios_grupo(escola_id, turno, titulo, data_inicio, data_fim, dia, observacao=None):
    aulas = listar_horarios_temporarios(escola_id, turno)
    observacao = (observacao or '').strip() or None
    return [
        aula for aula in aulas
        if str(aula.get('titulo')) == str(titulo)
        and str(aula.get('data_inicio')) == str(data_inicio)
        and str(aula.get('data_fim')) == str(data_fim or data_inicio)
        and str(aula.get('dia')) == str(dia)
        and ((aula.get('observacao') or None) == observacao)
    ]


def _agrupar_horarios_temporarios(aulas_temporarias):
    grupos = {}
    for aula in aulas_temporarias:
        chave = (
            aula.get('titulo'),
            aula.get('data_inicio'),
            aula.get('data_fim'),
            aula.get('dia'),
            aula.get('observacao'),
        )
        grupo = grupos.setdefault(chave, {
            'titulo': aula.get('titulo'),
            'data_inicio': aula.get('data_inicio'),
            'data_fim': aula.get('data_fim'),
            'dia': aula.get('dia'),
            'observacao': aula.get('observacao'),
            'total_aulas': 0,
            'turma_ids': set(),
            'criado_em': aula.get('criado_em'),
        })
        grupo['total_aulas'] += 1
        if aula.get('turma_id'):
            grupo['turma_ids'].add(int(aula['turma_id']))
        if aula.get('criado_em') and (not grupo.get('criado_em') or aula.get('criado_em') < grupo.get('criado_em')):
            grupo['criado_em'] = aula.get('criado_em')

    resultado = []
    for grupo in grupos.values():
        turma_ids = sorted(grupo.get('turma_ids') or [])
        grupo['turma_ids'] = turma_ids
        grupo['total_turmas'] = len(turma_ids)
        grupo['turma_id'] = turma_ids[0] if len(turma_ids) == 1 else None
        resultado.append(grupo)

    return sorted(
        resultado,
        key=lambda grupo: (
            str(grupo.get('data_inicio') or ''),
            str(grupo.get('data_fim') or ''),
            str(grupo.get('dia') or ''),
            str(grupo.get('titulo') or ''),
        ),
        reverse=True,
    )


def _horario_temporario_ativo_na_data(registro, data_referencia):
    data_inicio = _parse_date_or_today(registro.get('data_inicio'))
    data_fim = _parse_date_or_today(registro.get('data_fim') or registro.get('data_inicio'))
    return data_inicio <= data_referencia <= data_fim


def _geracao_oficial_travada_json(escola, turno):
    if not horario_turno_travado(escola, turno):
        return None
    return _json_error(
        'Geracao oficial travada. Destrave este turno antes de alterar o horario oficial.',
        status_code=423,
        code='official_schedule_locked',
    )


def _grupo_temporario_intersecta_intervalo(registro, inicio_intervalo, fim_intervalo):
    data_inicio = _parse_date_or_today(registro.get('data_inicio'))
    data_fim = _parse_date_or_today(registro.get('data_fim') or registro.get('data_inicio'))
    return data_inicio < fim_intervalo and data_fim >= inicio_intervalo


def _grupo_temporario_nao_vencido(registro, hoje=None):
    hoje = hoje or date.today()
    data_fim = _parse_date_or_today(registro.get('data_fim') or registro.get('data_inicio'))
    return data_fim >= hoje


def _camada_temporaria_key(registro):
    return (
        registro.get('titulo'),
        str(registro.get('data_inicio')),
        str(registro.get('data_fim')),
        registro.get('dia'),
        registro.get('observacao') or '',
    )


def _enriquecer_camadas_temporarias(escola_id, turno, camadas):
    if not camadas:
        return camadas

    aulas_por_grupo = {}
    for aula in listar_horarios_temporarios(escola_id, turno):
        aulas_por_grupo.setdefault(_camada_temporaria_key(aula), []).append(aula)

    for camada in camadas:
        aulas = aulas_por_grupo.get(_camada_temporaria_key(camada), [])
        turmas = sorted({aula.get('turma_nome') for aula in aulas if aula.get('turma_nome')})
        professores = sorted({aula.get('professor_nome') for aula in aulas if aula.get('professor_nome')})
        disciplinas = sorted({aula.get('disciplina_nome') for aula in aulas if aula.get('disciplina_nome')})
        periodos = sorted({int(aula.get('periodo')) for aula in aulas if aula.get('periodo')})
        primeira_aula = aulas[0] if len(aulas) == 1 else {}

        camada['turmas_nomes'] = turmas
        camada['professores_nomes'] = professores
        camada['disciplinas_nomes'] = disciplinas
        camada['periodos'] = periodos
        camada['modo_edicao'] = 'manual' if len(aulas) == 1 else 'auto'
        camada['professor_id'] = primeira_aula.get('professor_id')
        camada['disciplina_id'] = primeira_aula.get('disciplina_id')
        camada['periodo'] = primeira_aula.get('periodo')
        camada['tipo_operacao'] = 'Manual' if len(aulas) == 1 else 'Automático'
        camada['detalhe_resumo'] = ' · '.join(filter(None, [
            ', '.join(turmas[:2]) + (' +' if len(turmas) > 2 else '') if turmas else '',
            ', '.join(professores[:2]) + (' +' if len(professores) > 2 else '') if professores else '',
            ', '.join(disciplinas[:2]) + (' +' if len(disciplinas) > 2 else '') if disciplinas else '',
        ]))

    return camadas


def _month_bounds(month_value):
    try:
        inicio = datetime.strptime(str(month_value), '%Y-%m').date().replace(day=1)
    except (TypeError, ValueError):
        inicio = date.today().replace(day=1)

    if inicio.month == 12:
        fim = inicio.replace(year=inicio.year + 1, month=1, day=1)
    else:
        fim = inicio.replace(month=inicio.month + 1, day=1)
    return inicio, fim


def _default_report_date_for_month(month_value):
    inicio, fim = _month_bounds(month_value)
    hoje = date.today()
    if inicio <= hoje < fim:
        return hoje
    return inicio


def _resumir_ocorrencia_ativa(grupos_ativos):
    if not grupos_ativos:
        return None

    if len(grupos_ativos) == 1:
        resumo = dict(grupos_ativos[0])
        resumo['total_camadas'] = 1
        return resumo

    primeiro = grupos_ativos[0]
    turmas_por_grupo = {
        (
            grupo.get('titulo'),
            str(grupo.get('data_inicio')),
            str(grupo.get('data_fim')),
            grupo.get('dia'),
            grupo.get('observacao') or '',
        ): int(grupo.get('total_turmas') or 0)
        for grupo in grupos_ativos
    }
    return {
        'titulo': f'{len(grupos_ativos)} camadas temporárias',
        'dia': primeiro.get('dia'),
        'data_inicio': primeiro.get('data_inicio'),
        'data_fim': primeiro.get('data_fim'),
        'total_aulas': sum(int(grupo.get('total_aulas') or 0) for grupo in grupos_ativos),
        'total_turmas': sum(turmas_por_grupo.values()),
        'observacao': None,
        'total_camadas': len(grupos_ativos),
    }


def _guard_school(escola_id, permission='view_school', json_response=False):
    escola = _load_accessible_escola(escola_id)
    if not escola:
        if json_response:
            return None, _json_error('Escola não encontrada.', status_code=404, code='school_not_found')
        flash('Escola não encontrada.', 'error')
        return None, redirect(url_for('escola.home'))

    if not user_has_permission(g.user, permission):
        forbidden = forbid_without_school_permission(permission)
        return None, forbidden

    return escola, None


@dashboard_bp.route('/escola/<int:escola_id>/dashboard')
@login_required
def dashboard(escola_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    disciplinas = listar_disciplinas(escola_id, turno_atual)
    professores = listar_professores(escola_id, turno_atual)
    turmas = listar_turmas(escola_id, turno_atual)
    horario_balance = _build_horario_balance(turmas, professores)
    turno_atual_label = _turno_label(turno_atual)
    ai_audit_text = _build_ai_audit_text(escola, turno_atual, turno_atual_label, horario_balance, professores)
    return render_template(
        'dashboard.html',
        escola=escola,
        disciplinas=disciplinas,
        professores=professores,
        turmas=turmas,
        turnos=TURNOS,
        turno_atual=turno_atual,
        turno_atual_label=turno_atual_label,
        horario_balance=horario_balance,
        ai_audit_text=ai_audit_text,
        dias_semana=DIAS_SEMANA,
        cores_professor=CORES_PROFESSOR,
        cor_disciplina_padrao=COR_DISCIPLINA_PADRAO,
        cor_professor_padrao=COR_PROFESSOR_PADRAO,
    )


@dashboard_bp.route('/escola/<int:escola_id>/relatorios')
@login_required
def relatorios(escola_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    mes = request.args.get('mes') or _mes_atual()
    professores = listar_professores(escola['id'], turno_atual)
    try:
        registros = listar_relatorios_professores(escola['id'], turno_atual, mes)
    except RelatorioProfessorValidationError:
        mes = _mes_atual()
        registros = listar_relatorios_professores(escola['id'], turno_atual, mes)
        flash('Mês inválido. Exibindo o mês atual.', 'error')
    for registro in registros:
        registro['data_formatada'] = _format_date_br(registro.get('data_ocorrencia'))
    inicio_mes, fim_mes = _month_bounds(mes)
    data_registro_padrao = _default_report_date_for_month(mes)
    camadas_temporarias = [
        grupo for grupo in listar_grupos_horarios_temporarios(escola['id'], turno_atual)
        if _grupo_temporario_intersecta_intervalo(grupo, inicio_mes, fim_mes)
    ]
    _enriquecer_camadas_temporarias(escola['id'], turno_atual, camadas_temporarias)
    resumo_camadas = {
        'total': len(camadas_temporarias),
        'aulas': sum(int(grupo.get('total_aulas') or 0) for grupo in camadas_temporarias),
        'turmas': sum(int(grupo.get('total_turmas') or 0) for grupo in camadas_temporarias),
    }
    for grupo in camadas_temporarias:
        grupo['data_inicio_formatada'] = _format_date_br(grupo.get('data_inicio'))
        grupo['data_fim_formatada'] = _format_date_br(grupo.get('data_fim'))

    return render_template(
        'relatorios.html',
        escola=escola,
        professores=professores,
        registros=registros,
        resumo=_build_relatorios_summary(registros, professores),
        camadas_temporarias=camadas_temporarias,
        resumo_camadas=resumo_camadas,
        tipos_ocorrencia=TIPOS_OCORRENCIA,
        turnos=TURNOS,
        turno_atual=turno_atual,
        turno_atual_label=_turno_label(turno_atual),
        mes=mes,
        mes_label=_month_label(mes),
        inicio_mes=inicio_mes.isoformat(),
        fim_mes=(fim_mes - timedelta(days=1)).isoformat(),
        data_registro_padrao=data_registro_padrao.isoformat(),
        hoje=_data_atual(),
        can_manage_schedule=user_has_permission(g.user, 'manage_schedule'),
    )


@dashboard_bp.route('/escola/<int:escola_id>/prontuario')
@login_required
def prontuario(escola_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    status_filtro = request.args.get('status') or ''
    turmas = listar_turmas(escola['id'], turno_atual)
    professores = listar_professores(escola['id'], turno_atual)
    registros = listar_prontuarios(escola['id'], turno_atual, status_filtro)
    for registro in registros:
        registro['data_formatada'] = _format_date_br(registro.get('data_registro'))
        registro['feedback_formatado_em'] = _format_date_br(registro.get('feedback_em'))

    resumo = {
        'total': len(registros),
        'abertos': sum(1 for item in registros if item.get('status') == 'aberto'),
        'acompanhamento': sum(1 for item in registros if item.get('status') == 'em_acompanhamento'),
        'prioritarios': sum(1 for item in registros if item.get('prioridade') == 'alta'),
    }

    return render_template(
        'prontuario.html',
        escola=escola,
        turmas=turmas,
        professores=professores,
        registros=registros,
        resumo=resumo,
        turnos=TURNOS,
        turno_atual=turno_atual,
        turno_atual_label=_turno_label(turno_atual),
        status_filtro=status_filtro,
        status_options=STATUS_PRONTUARIO,
        prioridade_options=PRIORIDADES_PRONTUARIO,
        hoje=_data_atual(),
    )


@dashboard_bp.route('/escola/<int:escola_id>/prontuario/criar', methods=['POST'])
@login_required
def criar_prontuario_route(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_reports')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    try:
        criar_prontuario(
            escola['id'],
            turno_atual,
            request.form.get('aluno_nome'),
            request.form.get('turma_id'),
            request.form.get('observacao'),
            request.form.get('professor_marcado_id'),
            request.form.get('prioridade'),
            g.user.get('id'),
            request.form.get('data_registro'),
        )
        flash('Acompanhamento adicionado ao prontuario.', 'success')
    except ProntuarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao criar prontuario da escola %s.', escola['id'])
        flash('Não foi possível criar o acompanhamento agora.', 'error')

    return redirect(url_for('dashboard.prontuario', escola_id=escola_id, turno=turno_atual))


@dashboard_bp.route('/escola/<int:escola_id>/prontuario/<int:prontuario_id>/feedback', methods=['POST'])
@login_required
def feedback_prontuario_route(escola_id, prontuario_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    try:
        atualizado = registrar_feedback_prontuario(
            prontuario_id,
            escola['id'],
            turno_atual,
            request.form.get('feedback'),
            request.form.get('status'),
            g.user.get('id'),
        )
        flash('Feedback registrado.' if atualizado else 'Acompanhamento nao encontrado.', 'success' if atualizado else 'error')
    except ProntuarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao registrar feedback do prontuario %s da escola %s.', prontuario_id, escola['id'])
        flash('Não foi possível registrar o feedback agora.', 'error')

    return redirect(url_for('dashboard.prontuario', escola_id=escola_id, turno=turno_atual))


@dashboard_bp.route('/escola/<int:escola_id>/prontuario/<int:prontuario_id>/arquivar', methods=['POST'])
@login_required
def arquivar_prontuario_route(escola_id, prontuario_id):
    escola, failure = _guard_school(escola_id, permission='manage_reports')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    try:
        removido = arquivar_prontuario(prontuario_id, escola['id'], turno_atual, g.user.get('id'))
        flash('Acompanhamento arquivado.' if removido else 'Acompanhamento nao encontrado.', 'success' if removido else 'error')
    except Exception:
        current_app.logger.exception('Erro ao arquivar prontuario %s da escola %s.', prontuario_id, escola['id'])
        flash('Não foi possível arquivar o acompanhamento agora.', 'error')

    return redirect(url_for('dashboard.prontuario', escola_id=escola_id, turno=turno_atual))


@dashboard_bp.route('/escola/<int:escola_id>/relatorios/professores', methods=['POST'])
@login_required
def criar_relatorio_professor_route(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_reports')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    mes = request.form.get('mes') or _mes_atual()
    try:
        criar_relatorio_professor(
            escola['id'],
            turno_atual,
            request.form.get('professor_id'),
            request.form.get('data_ocorrencia'),
            request.form.get('tipo'),
            request.form.get('descricao'),
            g.user.get('id'),
        )
        flash('Registro adicionado ao relatório.', 'success')
        data_ocorrencia = _parse_date_or_today(request.form.get('data_ocorrencia'))
        mes = data_ocorrencia.strftime('%Y-%m')
    except RelatorioProfessorValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao criar relatório de professor da escola %s.', escola['id'])
        flash('Não foi possível registrar a falta ou ocorrência agora.', 'error')

    return redirect(url_for('dashboard.relatorios', escola_id=escola_id, turno=turno_atual, mes=mes))


@dashboard_bp.route('/escola/<int:escola_id>/relatorios/professores/<int:relatorio_id>/deletar', methods=['POST'])
@login_required
def deletar_relatorio_professor_route(escola_id, relatorio_id):
    escola, failure = _guard_school(escola_id, permission='manage_reports')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    mes = request.form.get('mes') or _mes_atual()
    try:
        removido = deletar_relatorio_professor(relatorio_id, escola['id'], turno_atual, g.user.get('id'))
        flash('Registro arquivado.' if removido else 'Registro não encontrado.', 'success' if removido else 'error')
    except Exception:
        current_app.logger.exception('Erro ao remover relatório de professor %s da escola %s.', relatorio_id, escola['id'])
        flash('Não foi possível remover o registro agora.', 'error')

    return redirect(url_for('dashboard.relatorios', escola_id=escola_id, turno=turno_atual, mes=mes))


@dashboard_bp.route('/escola/<int:escola_id>/relatorios/exportar/pdf')
@login_required
def exportar_relatorio_mensal(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    mes = request.args.get('mes') or _mes_atual()
    try:
        registros = listar_relatorios_professores(escola['id'], turno_atual, mes)
    except RelatorioProfessorValidationError:
        mes = _mes_atual()
        registros = listar_relatorios_professores(escola['id'], turno_atual, mes)

    for registro in registros:
        registro['data_formatada'] = _format_date_br(registro.get('data_ocorrencia'))

    inicio_mes, fim_mes = _month_bounds(mes)
    camadas_temporarias = [
        grupo for grupo in listar_grupos_horarios_temporarios(escola['id'], turno_atual)
        if _grupo_temporario_intersecta_intervalo(grupo, inicio_mes, fim_mes)
    ]
    _enriquecer_camadas_temporarias(escola['id'], turno_atual, camadas_temporarias)
    for grupo in camadas_temporarias:
        grupo['data_inicio_formatada'] = _format_date_br(grupo.get('data_inicio'))
        grupo['data_fim_formatada'] = _format_date_br(grupo.get('data_fim'))

    resumo_camadas = {
        'total': len(camadas_temporarias),
        'aulas': sum(int(grupo.get('total_aulas') or 0) for grupo in camadas_temporarias),
        'turmas': sum(int(grupo.get('total_turmas') or 0) for grupo in camadas_temporarias),
    }
    professores = listar_professores(escola['id'], turno_atual)
    filepath = exportar_relatorio_mensal_pdf(
        escola,
        _turno_label(turno_atual),
        _month_label(mes),
        registros,
        _build_relatorios_summary(registros, professores),
        camadas_temporarias,
        resumo_camadas,
        TIPOS_OCORRENCIA,
    )
    return _send_temp_file(filepath, f'relatorio-{turno_atual}-{mes}.pdf')


@dashboard_bp.route('/escola/<int:escola_id>/disciplina/criar', methods=['POST'])
@login_required
def criar_disc(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#22c55e').strip()
    if not nome:
        flash('Nome da disciplina é obrigatório.', 'error')
    else:
        sucesso, msg = criar_disciplina(escola['id'], nome, cor, _active_turno())
        flash(msg, 'success' if sucesso else 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='disciplinas'))


@dashboard_bp.route('/escola/<int:escola_id>/disciplina/<int:disc_id>/editar', methods=['POST'])
@login_required
def editar_disc(escola_id, disc_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#22c55e').strip()
    if nome:
        try:
            atualizar_disciplina(disc_id, escola['id'], nome, cor, _active_turno())
            flash('Disciplina atualizada.', 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='disciplinas'))


@dashboard_bp.route('/escola/<int:escola_id>/disciplina/<int:disc_id>/deletar', methods=['POST'])
@login_required
def deletar_disc(escola_id, disc_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    try:
        deletar_disciplina(disc_id, escola['id'])
        flash('Disciplina removida.', 'success')
    except DisciplineInUseError as exc:
        flash(str(exc), 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='disciplinas'))


@dashboard_bp.route('/escola/<int:escola_id>/professor/criar', methods=['POST'])
@login_required
def criar_prof(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '').strip()
    dias = request.form.getlist('dias_disponiveis')
    cargas = _parse_cargas_professor(request.form)
    max_aulas = _calcular_max_aulas_professor(cargas)
    disciplina_ids = sorted(set(request.form.getlist('disciplina_ids') + [
        str(carga['disciplina_id']) for carga in cargas
    ]))
    turma_ids = sorted(set(request.form.getlist('turma_ids') + [
        str(carga['turma_id']) for carga in cargas
    ]))
    if not nome or not disciplina_ids:
        flash('Nome e pelo menos uma disciplina são obrigatórios.', 'error')
    elif not dias:
        flash('Selecione pelo menos um dia disponível.', 'error')
    elif not turma_ids:
        flash('Selecione pelo menos uma turma para vincular ao professor.', 'error')
    else:
        sucesso, msg = criar_professor(escola['id'], nome, disciplina_ids, max_aulas, dias, turma_ids, cargas, cor, _active_turno())
        flash(msg, 'success' if sucesso else 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='professores'))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/editar', methods=['POST'])
@login_required
def editar_prof(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '').strip()
    dias = request.form.getlist('dias_disponiveis')
    cargas = _parse_cargas_professor(request.form)
    max_aulas = _calcular_max_aulas_professor(cargas)
    disciplina_ids = sorted(set(request.form.getlist('disciplina_ids') + [
        str(carga['disciplina_id']) for carga in cargas
    ]))
    turma_ids = sorted(set(request.form.getlist('turma_ids') + [
        str(carga['turma_id']) for carga in cargas
    ]))
    if nome and disciplina_ids and dias and turma_ids:
        try:
            atualizar_professor(prof_id, escola['id'], nome, disciplina_ids, max_aulas, dias, turma_ids, cargas, cor, _active_turno())
            flash('Professor atualizado.', 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
    else:
        flash('Preencha nome, disciplinas, dias disponiveis e pelo menos uma turma.', 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='professores'))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/deletar', methods=['POST'])
@login_required
def deletar_prof(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    deletar_professor(prof_id, escola['id'])
    flash('Professor removido.', 'success')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='professores'))


@dashboard_bp.route('/escola/<int:escola_id>/turma/criar', methods=['POST'])
@login_required
def criar_turm(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    aulas_por_dia = request.form.get('aulas_por_dia', 5)
    if not nome:
        flash('Nome da turma é obrigatório.', 'error')
    else:
        sucesso, msg = criar_turma(escola['id'], nome, aulas_por_dia, _active_turno())
        flash(msg, 'success' if sucesso else 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='turmas'))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/editar', methods=['POST'])
@login_required
def editar_turm(escola_id, turma_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    aulas_por_dia = request.form.get('aulas_por_dia', 5)
    if nome:
        try:
            atualizar_turma(turma_id, escola['id'], nome, aulas_por_dia, _active_turno())
            flash('Turma atualizada.', 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='turmas'))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/deletar', methods=['POST'])
@login_required
def deletar_turm(escola_id, turma_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    deletar_turma(turma_id, escola['id'])
    flash('Turma removida.', 'success')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id, _anchor='turmas'))


@dashboard_bp.route('/escola/<int:escola_id>/horarios')
@login_required
def horarios(escola_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    horario_oficial_travado = horario_turno_travado(escola, turno_atual)
    data_visualizada = _parse_date_or_today(request.args.get('data'))
    data_visualizada_iso = data_visualizada.isoformat()
    view_mode = request.args.get('view', 'turma')
    if view_mode != 'geral':
        view_mode = 'turma'
    visualizacao_horario = request.args.get('visualizacao', 'alternativo')
    if visualizacao_horario not in {'oficial', 'alternativo'}:
        visualizacao_horario = 'alternativo'
    dia_visualizado = DIAS_SEMANA[data_visualizada.weekday()] if data_visualizada.weekday() < len(DIAS_SEMANA) else None
    turmas = listar_turmas(escola['id'], turno_atual)
    aulas = listar_aulas(escola['id'], turno_atual)
    disciplinas = listar_disciplinas(escola['id'], turno_atual)
    professores = listar_professores(escola['id'], turno_atual)
    turmas_por_turno = {
        turno['id']: listar_turmas(escola['id'], turno['id'])
        for turno in TURNOS
    }
    professores_por_turno = {
        turno['id']: listar_professores(escola['id'], turno['id'])
        for turno in TURNOS
    }
    aulas_por_turno = {
        turno['id']: (aulas if turno['id'] == turno_atual else listar_aulas(escola['id'], turno['id']))
        for turno in TURNOS
    }

    grade = {}
    for turma in turmas:
        periodos_turma = list(range(1, int(turma.get('aulas_por_dia') or 5) + 1))
        grade[turma['id']] = {dia: {p: None for p in periodos_turma} for dia in DIAS_SEMANA}

    for aula in aulas:
        tid = aula['turma_id']
        dia = aula['dia']
        per = aula['periodo']
        if tid in grade and dia in grade[tid]:
            grade[tid][dia][per] = aula

    turma_selecionada_id = request.args.get('turma_id', type=int)
    if not turma_selecionada_id and turmas:
        turma_selecionada_id = turmas[0]['id']
    turma_selecionada = next((turma for turma in turmas if turma['id'] == turma_selecionada_id), None)
    periodos_turma = list(range(1, int((turma_selecionada or {}).get('aulas_por_dia') or 5) + 1))
    horarios_temporarios = listar_horarios_temporarios(
        escola['id'],
        turno_atual,
        turma_selecionada_id if turma_selecionada and view_mode != 'geral' else None,
    )
    horarios_temporarios_ativos = [
        horario for horario in horarios_temporarios
        if visualizacao_horario == 'alternativo'
        and _horario_temporario_ativo_na_data(horario, data_visualizada)
        and dia_visualizado
        and horario.get('dia') == dia_visualizado
    ]
    grupos_horarios_temporarios = listar_grupos_horarios_temporarios(escola['id'], turno_atual)
    if view_mode != 'geral':
        grupos_horarios_temporarios = _agrupar_horarios_temporarios(horarios_temporarios)
    grupos_horarios_temporarios = [
        grupo for grupo in grupos_horarios_temporarios
        if _grupo_temporario_nao_vencido(grupo, hoje=data_visualizada)
    ]
    for grupo in grupos_horarios_temporarios:
        grupo['ativo_na_data'] = _horario_temporario_ativo_na_data(grupo, data_visualizada)
        grupo['data_inicio_formatada'] = _format_date_br(grupo.get('data_inicio'))
        grupo['data_fim_formatada'] = _format_date_br(grupo.get('data_fim'))
    grupos_ativos = [
        grupo for grupo in grupos_horarios_temporarios
        if grupo.get('ativo_na_data')
        and dia_visualizado
        and grupo.get('dia') == dia_visualizado
    ]
    ocorrencia_ativa = _resumir_ocorrencia_ativa(grupos_ativos) if visualizacao_horario == 'alternativo' else None
    temporarios_por_slot = {}
    temporarios_por_turma_slot = {}
    for horario_temp in horarios_temporarios_ativos:
        chave = f"{horario_temp['dia']}:{horario_temp['periodo']}"
        temporarios_por_slot.setdefault(chave, []).append(horario_temp)
        chave_turma = f"{horario_temp['turma_id']}:{horario_temp['dia']}:{horario_temp['periodo']}"
        temporarios_por_turma_slot.setdefault(chave_turma, []).append(horario_temp)

    return render_template(
        'horarios.html',
        escola=escola,
        turmas=turmas,
        grade=grade,
        aulas=aulas,
        disciplinas=disciplinas,
        professores=professores,
        turma_selecionada=turma_selecionada,
        horarios_temporarios=horarios_temporarios_ativos,
        grupos_horarios_temporarios=grupos_horarios_temporarios,
        grupos_horarios_temporarios_ativos=grupos_ativos,
        ocorrencia_ativa=ocorrencia_ativa,
        temporarios_por_slot=temporarios_por_slot,
        temporarios_por_turma_slot=temporarios_por_turma_slot,
        turmas_por_turno=turmas_por_turno,
        professores_por_turno=professores_por_turno,
        dias=DIAS_SEMANA,
        periodos=periodos_turma,
        periodos_alternativo=PERIODOS,
        turma_selecionada_id=turma_selecionada_id,
        manual_options=_build_manual_options(turmas, professores, aulas),
        alternative_manual_options=_build_alternative_manual_options(professores_por_turno),
        alternative_occupied_slots=_build_alternative_occupied_slots(aulas_por_turno),
        alternative_official_lessons=_build_alternative_official_lessons(aulas_por_turno),
        view_mode=view_mode,
        visualizacao_horario=visualizacao_horario,
        turnos=TURNOS,
        turno_atual=turno_atual,
        turno_atual_label=_turno_label(turno_atual),
        horario_oficial_travado=horario_oficial_travado,
        data_visualizada=data_visualizada_iso,
        data_visualizada_formatada=_format_date_br(data_visualizada),
        hoje=_data_atual(),
    )


@dashboard_bp.route('/escola/<int:escola_id>/horarios/trava', methods=['POST'])
@login_required
def alternar_trava_horario(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    travar = request.form.get('acao') != 'destravar'
    definir_horario_turno_travado(escola['id'], turno_atual, travar)
    flash(
        'Geracao oficial travada para este turno.'
        if travar else
        'Geracao oficial destravada para este turno.',
        'success',
    )

    turma_id = request.form.get('turma_id', type=int)
    data_visualizada = request.form.get('data_visualizada') or request.args.get('data')
    visualizacao = request.form.get('visualizacao') or request.args.get('visualizacao') or 'alternativo'
    view_mode = request.form.get('view') or request.args.get('view')
    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, data=data_visualizada, visualizacao=visualizacao))
    if view_mode == 'geral':
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', data=data_visualizada, visualizacao=visualizacao))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, data=data_visualizada, visualizacao=visualizacao))


@dashboard_bp.route('/escola/<int:escola_id>/gerar', methods=['POST'])
@login_required
def gerar(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    turno_atual = _active_turno()
    if horario_turno_travado(escola, turno_atual):
        flash('Geracao oficial travada. Destrave este turno antes de gerar um novo horario oficial.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral'))
    try:
        sucesso, msg, total = gerar_horario(escola['id'], turma_id, turno_atual)
    except Exception:
        current_app.logger.exception(
            'Erro inesperado ao gerar horário da escola %s, turma %s.',
            escola['id'],
            turma_id,
        )
        sucesso = False
        msg = (
            'Não foi possível gerar o horário agora. '
            'Verifique se as aulas, professores e turmas estão consistentes e tente novamente.'
        )
    flash(msg, 'success' if sucesso else 'error')
    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/temporario/gerar', methods=['POST'])
@login_required
def gerar_temporario(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    turma_id_contexto = request.form.get('turma_contexto_id', type=int)
    turma_id = request.form.get('turma_id', type=int)
    data_inicio = request.form.get('data_inicio')
    data_fim = request.form.get('data_fim') or data_inicio
    titulo = request.form.get('motivo') or 'Horário alternativo'
    professor_excluido_id = request.form.get('professor_excluido_id', type=int)
    periodo_bloqueado = request.form.get('periodo_bloqueado', type=int)
    redirect_values = {'data': data_inicio, 'visualizacao': 'alternativo'}
    data_inicio_parsed = _parse_date_or_today(data_inicio)
    data_fim_parsed = _parse_date_or_today(data_fim)
    if data_fim_parsed < data_inicio_parsed:
        flash('A data final nao pode ser anterior a data inicial.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        if turma_id_contexto and turno_atual == request.args.get('turno'):
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id_contexto, **redirect_values))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))
    dias_selecionados = _dias_letivos_no_intervalo(data_inicio_parsed, data_fim_parsed)
    if _date_range_has_weekend(data_inicio_parsed, data_fim_parsed):
        flash('Não é permitido criar camadas temporárias para sábado ou domingo.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        if turma_id_contexto and turno_atual == request.args.get('turno'):
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id_contexto, **redirect_values))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    if not professor_excluido_id and not periodo_bloqueado:
        flash('Selecione um professor ausente ou um periodo bloqueado para criar uma camada temporaria.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        if turma_id_contexto and turno_atual == request.args.get('turno'):
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id_contexto, **redirect_values))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    if not dias_selecionados:
        flash('Escolha uma data entre segunda e sexta.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        if turma_id_contexto and turno_atual == request.args.get('turno'):
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id_contexto, **redirect_values))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    turmas_turno = listar_turmas(escola['id'], turno_atual)
    turma_selecionada = next((turma for turma in turmas_turno if int(turma['id']) == int(turma_id or 0)), None)
    if turma_id and not turma_selecionada:
        flash('Selecione uma turma valida para este turno.', 'error')
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    if turma_selecionada and periodo_bloqueado:
        aulas_por_dia = int(turma_selecionada.get('aulas_por_dia') or 5)
        if periodo_bloqueado > aulas_por_dia:
            flash('Selecione um periodo valido para a turma escolhida.', 'error')
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))

    aulas_no_alcance = [
        aula for aula in listar_aulas(escola['id'], turno_atual)
        if aula.get('dia') in dias_selecionados
        and (not turma_id or int(aula.get('turma_id') or 0) == int(turma_id))
    ]
    if not aulas_no_alcance:
        flash('Não há aulas oficiais no alcance selecionado para gerar alternativo.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    if periodo_bloqueado and not any(int(aula.get('periodo') or 0) == int(periodo_bloqueado) for aula in aulas_no_alcance):
        flash('Não há aula oficial nesse período para o alcance selecionado.', 'error')
        if turma_id:
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    professores_turno = listar_professores(escola['id'], turno_atual)
    professor = None
    if professor_excluido_id:
        professor = next(
            (prof for prof in professores_turno if int(prof['id']) == int(professor_excluido_id)),
            None,
        )
        if not professor:
            flash('Selecione um professor valido para este turno.', 'error')
            if turma_id:
                return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))
        if turma_id and not _professor_ministra_na_turma(professor, turma_id):
            flash('Este professor nao possui aulas cadastradas para a turma escolhida.', 'error')
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
        if not any(int(aula.get('professor_id') or 0) == int(professor_excluido_id) for aula in aulas_no_alcance):
            flash('Este professor nao possui aula oficial no alcance selecionado.', 'error')
            if turma_id:
                return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))

    observacao_partes = []
    if turma_selecionada:
        observacao_partes.append(f"Turma: {turma_selecionada['nome']}")
    if professor_excluido_id:
        observacao_partes.append(f"Sem {professor['nome'] if professor else 'professor selecionado'}")
    if periodo_bloqueado:
        observacao_partes.append(f"Pulando {periodo_bloqueado}º período")
    observacao = '; '.join(observacao_partes) or None

    try:
        total_geral = 0
        dias_criados = []
        dias_sem_aulas = []
        dias_sem_impacto = []
        for dia_item in dias_selecionados:
            aulas_geradas_item = _montar_aulas_alternativas_do_dia(
                escola['id'],
                turno_atual,
                dia_item,
                turma_id,
                professor_excluido_id,
                periodo_bloqueado,
            )
            if aulas_geradas_item is None:
                dias_sem_aulas.append(dia_item)
                continue
            if not aulas_geradas_item:
                dias_sem_impacto.append(dia_item)
                continue
            total_item = criar_horarios_temporarios_lote(
                escola['id'],
                turno_atual,
                data_inicio,
                data_fim,
                dia_item,
                titulo,
                aulas_geradas_item,
                observacao,
            )
            total_geral += total_item
            dias_criados.append(dia_item)

        if dias_criados:
            flash(
                f'Camada temporaria criada para {", ".join(dias_criados)}: {total_geral} aula(s) temporaria(s).',
                'success',
            )
        if dias_sem_aulas:
            flash(f'Sem aulas oficiais em: {", ".join(dias_sem_aulas)}.', 'warning')
        if dias_sem_impacto:
            flash(
                f'Nenhuma aula foi afetada em: {", ".join(dias_sem_impacto)}. Verifique professor, turma ou periodo.',
                'warning',
            )
        if not dias_criados:
            flash('Nenhuma camada temporaria foi criada.', 'error')
    except HorarioTemporarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao gerar horario temporario da escola %s.', escola['id'])
        flash(
            'Não foi possível gerar o horário alternativo agora. '
            'Verifique se as aulas, professores e turmas estão consistentes e tente novamente.',
            'error',
        )

    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, **redirect_values))
    if turma_id_contexto and turno_atual == request.args.get('turno'):
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id_contexto, **redirect_values))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', **redirect_values))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/limpar', methods=['POST'])
@login_required
def limpar_horarios(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turno_atual = _active_turno()
    if horario_turno_travado(escola, turno_atual):
        flash('Geracao oficial travada. Destrave este turno antes de limpar o horario oficial.', 'error')
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral'))

    alvo = request.form.get('limpar_alvo', 'todas')
    limpar_turma_id = None
    if alvo != 'todas':
        try:
            limpar_turma_id = int(alvo)
        except (TypeError, ValueError):
            flash('Selecione uma turma válida para limpar.', 'error')
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral'))
    try:
        limpar_aulas(escola['id'], limpar_turma_id, turno_atual)
        flash(
            'Horários da turma limpos.' if limpar_turma_id else 'Horários de todas as turmas limpos.',
            'success',
        )
    except Exception:
        current_app.logger.exception('Erro ao limpar horários da escola %s.', escola['id'])
        flash('Não foi possível limpar os horários agora.', 'error')

    if limpar_turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=limpar_turma_id))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral'))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/manual', methods=['POST'])
@login_required
def criar_manual(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule', json_response=True)
    if failure:
        return failure

    turno_atual = _active_turno()
    locked = _geracao_oficial_travada_json(escola, turno_atual)
    if locked:
        return locked

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error('Corpo da requisição inválido.', code='invalid_payload')

    try:
        aula_id = criar_aula_manual(
            escola['id'],
            int(data.get('turma_id')),
            int(data.get('professor_id')),
            int(data.get('disciplina_id')),
            str(data.get('dia')),
            int(data.get('periodo')),
            turno_atual,
        )
    except ScheduleConflictError as exc:
        return _json_error(str(exc), code='schedule_conflict')
    except ScheduleValidationError as exc:
        return _json_error(str(exc), code='schedule_validation')
    except (TypeError, ValueError):
        return _json_error('Dados obrigatórios inválidos.', code='invalid_payload')

    aula = next(
        (dict(item) for item in listar_aulas(escola['id'], turno_atual) if int(item['id']) == int(aula_id)),
        None,
    )

    return jsonify({'status': 'ok', 'aula_id': aula_id, 'aula': aula})


@dashboard_bp.route('/escola/<int:escola_id>/horarios/aula/<int:aula_id>/deletar', methods=['POST'])
@login_required
def deletar_aula_manual(escola_id, aula_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule', json_response=True)
    if failure:
        return failure

    turno_atual = _active_turno()
    locked = _geracao_oficial_travada_json(escola, turno_atual)
    if locked:
        return locked

    try:
        aula_removida = deletar_aula(aula_id, escola_id=escola['id'], turno=turno_atual)
    except Exception:
        current_app.logger.exception('Erro ao remover aula %s da escola %s.', aula_id, escola['id'])
        return _json_error('Não foi possível remover a aula agora.', code='delete_failed')

    if not aula_removida:
        return _json_error('Aula não encontrada.', status_code=404, code='not_found')

    return jsonify({'status': 'ok', 'aula': aula_removida})


@dashboard_bp.route('/escola/<int:escola_id>/horarios/temporario', methods=['POST'])
@login_required
def criar_temporario(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    turno_atual = normalizar_turno(request.form.get('turno') or _active_turno())
    data_inicio = request.form.get('data_inicio')
    data_inicio_parsed = _parse_date_or_today(data_inicio)
    dia = (
        DIAS_SEMANA[data_inicio_parsed.weekday()]
        if data_inicio_parsed.weekday() < len(DIAS_SEMANA)
        else None
    )
    try:
        if not dia:
            raise HorarioTemporarioValidationError("Escolha uma data entre segunda e sexta.")
        criar_horario_temporario(
            escola['id'],
            turno_atual,
            turma_id,
            data_inicio,
            request.form.get('data_fim') or data_inicio,
            dia,
            request.form.get('periodo', type=int),
            request.form.get('titulo'),
            request.form.get('professor_id', type=int),
            request.form.get('disciplina_id', type=int),
            request.form.get('observacao'),
        )
        flash('Horario temporario criado sem alterar o horario oficial.', 'success')
    except HorarioTemporarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao criar horario temporario da escola %s.', escola['id'])
        flash('Não foi possível criar o horário temporário agora.', 'error')

    data_visualizada = data_inicio or request.form.get('data_visualizada')
    return redirect(_dashboard_url(
        'dashboard.horarios',
        escola_id=escola_id,
        turma_id=turma_id,
        turno=turno_atual,
        data=data_visualizada,
        visualizacao='alternativo',
    ))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/temporario/<int:horario_id>/deletar', methods=['POST'])
@login_required
def deletar_temporario(escola_id, horario_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    try:
        removido = deletar_horario_temporario(horario_id, escola['id'], _active_turno())
        flash('Horário temporário removido.' if removido else 'Horário temporário não encontrado.', 'success' if removido else 'error')
    except Exception:
        current_app.logger.exception('Erro ao remover horario temporario %s da escola %s.', horario_id, escola['id'])
        flash('Não foi possível remover o horário temporário agora.', 'error')

    data_visualizada = request.form.get('data_visualizada') or request.args.get('data')
    visualizacao = request.form.get('visualizacao') or request.args.get('visualizacao') or 'alternativo'
    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, data=data_visualizada, visualizacao=visualizacao))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, data=data_visualizada, visualizacao=visualizacao))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/temporario/grupo/deletar', methods=['POST'])
@login_required
def deletar_temporario_grupo(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    try:
        removidos = deletar_horarios_temporarios_grupo(
            escola['id'],
            _active_turno(),
            request.form.get('titulo'),
            request.form.get('data_inicio'),
            request.form.get('data_fim') or request.form.get('data_inicio'),
            request.form.get('dia'),
            request.form.get('observacao'),
        )
        flash(
            f'Horário alternativo removido: {removidos} aula(s).' if removidos else 'Horário alternativo não encontrado.',
            'success' if removidos else 'error',
        )
    except HorarioTemporarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao remover grupo de horario temporario da escola %s.', escola['id'])
        flash('Não foi possível remover o horário alternativo agora.', 'error')

    turma_id = request.form.get('turma_id', type=int)
    data_visualizada = request.form.get('data_visualizada') or request.args.get('data')
    view_mode = request.form.get('view') or request.args.get('view')
    visualizacao = request.form.get('visualizacao') or request.args.get('visualizacao') or 'alternativo'
    if request.form.get('redirect_to') == 'relatorios':
        return redirect(_dashboard_url(
            'dashboard.relatorios',
            escola_id=escola_id,
            turno=_active_turno(),
            mes=request.form.get('mes') or _mes_atual(),
        ))
    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id, data=data_visualizada, visualizacao=visualizacao))
    if view_mode == 'geral':
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral', data=data_visualizada, visualizacao=visualizacao))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, data=data_visualizada, visualizacao=visualizacao))


@dashboard_bp.route('/escola/<int:escola_id>/mover_aula', methods=['POST'])
@login_required
def mover(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule', json_response=True)
    if failure:
        return failure

    locked = _geracao_oficial_travada_json(escola, _active_turno())
    if locked:
        return locked

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error('Corpo da requisição inválido.', code='invalid_payload')

    aula_id = data.get('aula_id')
    novo_dia = data.get('dia')
    novo_periodo = data.get('periodo')

    if aula_id is None or novo_dia is None or novo_periodo is None:
        return _json_error('Dados obrigatórios ausentes.', code='invalid_payload')

    try:
        resultado = mover_aula(int(aula_id), str(novo_dia), int(novo_periodo), escola_id=escola['id'])
    except ScheduleConflictError as exc:
        return _json_error(str(exc), code='schedule_conflict')
    except ScheduleValidationError as exc:
        return _json_error(str(exc), code='schedule_validation')
    except ValueError:
        return _json_error('IDs e períodos devem ser numéricos.', code='invalid_payload')

    return jsonify({'status': 'ok', **(resultado or {})})


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/ocupacao')
@login_required
def ocupacao_professor(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='view_school', json_response=True)
    if failure:
        return failure

    aulas = listar_aulas(escola['id'], _active_turno())
    ocupacao = []
    for aula in aulas:
        if aula['professor_id'] == prof_id:
            ocupacao.append({
                'aula_id': aula['id'],
                'dia': aula['dia'],
                'periodo': aula['periodo'],
                'turma_id': aula['turma_id'],
                'turma_nome': aula['turma_nome'],
            })
    return jsonify(ocupacao)


def _export_color_mode():
    mode = request.args.get('color_mode', 'disciplina')
    return mode if mode in {'disciplina', 'professor', 'none'} else 'disciplina'


@dashboard_bp.route('/escola/<int:escola_id>/exportar/excel')
@login_required
def exportar_xls(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas = listar_aulas(escola['id'], turno_atual)
    turmas = listar_turmas(escola['id'], turno_atual)
    filepath = exportar_excel(escola, aulas, turmas, color_mode=_export_color_mode())
    return _send_temp_file(filepath, f'horario-{turno_atual}.xlsx')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/pdf')
@login_required
def exportar_pdf_route(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas = listar_aulas(escola['id'], turno_atual)
    turmas = listar_turmas(escola['id'], turno_atual)
    disciplinas = listar_disciplinas(escola['id'], turno_atual)
    filepath = exportar_pdf(
        escola,
        aulas,
        turmas,
        disciplinas,
        color_mode=_export_color_mode(),
        transpor_grade=True,
    )
    return _send_temp_file(filepath, f'horario-{turno_atual}.pdf')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/pdf/geral')
@login_required
def exportar_pdf_geral_route(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas = listar_aulas(escola['id'], turno_atual)
    turmas = listar_turmas(escola['id'], turno_atual)
    filepath = exportar_pdf_matriz(escola, aulas, turmas, color_mode=_export_color_mode())
    return _send_temp_file(filepath, f'horario-geral-{turno_atual}.pdf')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/temporario/excel')
@login_required
def exportar_temporario_xls(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas_temporarias = _filtrar_horarios_temporarios_grupo(
        escola['id'],
        turno_atual,
        request.args.get('titulo'),
        request.args.get('data_inicio'),
        request.args.get('data_fim') or request.args.get('data_inicio'),
        request.args.get('dia'),
        request.args.get('observacao'),
    )
    aulas, turmas = _mesclar_aulas_oficiais_com_alternativas(escola['id'], turno_atual, aulas_temporarias)
    filepath = exportar_excel(escola, aulas, turmas, color_mode=_export_color_mode())
    return _send_temp_file(filepath, f'horario-alternativo-{turno_atual}.xlsx')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/temporario/pdf')
@login_required
def exportar_temporario_pdf(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas_temporarias = _filtrar_horarios_temporarios_grupo(
        escola['id'],
        turno_atual,
        request.args.get('titulo'),
        request.args.get('data_inicio'),
        request.args.get('data_fim') or request.args.get('data_inicio'),
        request.args.get('dia'),
        request.args.get('observacao'),
    )
    aulas, turmas = _mesclar_aulas_oficiais_com_alternativas(escola['id'], turno_atual, aulas_temporarias)
    disciplinas = listar_disciplinas(escola['id'], turno_atual)
    filepath = exportar_pdf(
        escola,
        aulas,
        turmas,
        disciplinas,
        color_mode=_export_color_mode(),
        transpor_grade=True,
    )
    return _send_temp_file(filepath, f'horario-alternativo-{turno_atual}.pdf')
