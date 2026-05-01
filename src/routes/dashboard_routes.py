import os

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
from exports.pdf_export import exportar_pdf, exportar_pdf_matriz
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
from models.escola import buscar_escola
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
from models.turma import atualizar_turma, criar_turma, deletar_turma, listar_turmas
from models.turno import TURNOS, normalizar_turno
from scheduler import gerar_horario, montar_horario_gerado


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


def _load_accessible_escola(escola_id):
    return buscar_escola(escola_id, user=g.user)


def _active_turno():
    return normalizar_turno(request.values.get('turno') or request.args.get('turno'))


def _turno_label(turno_id):
    turno_id = normalizar_turno(turno_id)
    return next((turno['nome'] for turno in TURNOS if turno['id'] == turno_id), 'Matutino')


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
    aulas_mantidas = []
    for aula in aulas_dia:
        slot = (aula['turma_id'], aula['periodo'])
        if periodo_bloqueado and aula['periodo'] == periodo_bloqueado:
            aulas_mantidas.append({
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
        aulas_mantidas.append(aula)

    if not precisa_substituir:
        return aulas_mantidas

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

    return aulas_mantidas + list(substitutas.values()) + sem_substituta


def _normalizar_aulas_temporarias_para_export(aulas_temporarias):
    aulas = []
    for aula in aulas_temporarias:
        titulo = aula.get('titulo') or 'Horario alternativo'
        aulas.append({
            **aula,
            'disciplina_nome': aula.get('disciplina_nome') or titulo,
            'professor_nome': aula.get('professor_nome') or (aula.get('observacao') or 'Sem professor definido'),
            'disciplina_cor': aula.get('disciplina_cor') or '#eab308',
            'professor_cor': aula.get('professor_cor') or '#eab308',
        })
    return aulas


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
    return render_template(
        'dashboard.html',
        escola=escola,
        disciplinas=disciplinas,
        professores=professores,
        turmas=turmas,
        turnos=TURNOS,
        turno_atual=turno_atual,
        turno_atual_label=_turno_label(turno_atual),
        horario_balance=horario_balance,
        dias_semana=DIAS_SEMANA,
        cores_professor=CORES_PROFESSOR,
        cor_disciplina_padrao=COR_DISCIPLINA_PADRAO,
        cor_professor_padrao=COR_PROFESSOR_PADRAO,
    )


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
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/disciplina/<int:disc_id>/editar', methods=['POST'])
@login_required
def editar_disc(escola_id, disc_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#22c55e').strip()
    if nome:
        atualizar_disciplina(disc_id, escola['id'], nome, cor)
        flash('Disciplina atualizada.', 'success')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


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
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


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
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


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
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/deletar', methods=['POST'])
@login_required
def deletar_prof(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    deletar_professor(prof_id, escola['id'])
    flash('Professor removido.', 'success')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


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
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/editar', methods=['POST'])
@login_required
def editar_turm(escola_id, turma_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    aulas_por_dia = request.form.get('aulas_por_dia', 5)
    if nome:
        atualizar_turma(turma_id, escola['id'], nome, aulas_por_dia)
        flash('Turma atualizada.', 'success')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/deletar', methods=['POST'])
@login_required
def deletar_turm(escola_id, turma_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    deletar_turma(turma_id, escola['id'])
    flash('Turma removida.', 'success')
    return redirect(_dashboard_url('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/horarios')
@login_required
def horarios(escola_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    turmas = listar_turmas(escola['id'], turno_atual)
    aulas = listar_aulas(escola['id'], turno_atual)
    disciplinas = listar_disciplinas(escola['id'], turno_atual)
    professores = listar_professores(escola['id'], turno_atual)

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
        turma_selecionada_id if turma_selecionada else None,
    )
    grupos_horarios_temporarios = listar_grupos_horarios_temporarios(escola['id'], turno_atual)
    temporarios_por_slot = {}
    for horario_temp in horarios_temporarios:
        chave = f"{horario_temp['dia']}:{horario_temp['periodo']}"
        temporarios_por_slot.setdefault(chave, []).append(horario_temp)
    view_mode = request.args.get('view', 'turma')
    if view_mode != 'geral':
        view_mode = 'turma'

    return render_template(
        'horarios.html',
        escola=escola,
        turmas=turmas,
        grade=grade,
        aulas=aulas,
        disciplinas=disciplinas,
        professores=professores,
        horarios_temporarios=horarios_temporarios,
        grupos_horarios_temporarios=grupos_horarios_temporarios,
        temporarios_por_slot=temporarios_por_slot,
        dias=DIAS_SEMANA,
        periodos=periodos_turma,
        turma_selecionada_id=turma_selecionada_id,
        manual_options=_build_manual_options(turmas, professores, aulas),
        view_mode=view_mode,
        turnos=TURNOS,
        turno_atual=turno_atual,
        turno_atual_label=_turno_label(turno_atual),
    )


@dashboard_bp.route('/escola/<int:escola_id>/gerar', methods=['POST'])
@login_required
def gerar(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    try:
        sucesso, msg, total = gerar_horario(escola['id'], turma_id, _active_turno())
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

    turno_atual = _active_turno()
    turma_id_contexto = request.form.get('turma_contexto_id', type=int)
    turma_id = request.form.get('turma_id', type=int)
    data_inicio = request.form.get('data_inicio')
    data_fim = request.form.get('data_fim') or data_inicio
    dia = request.form.get('dia')
    titulo = request.form.get('motivo') or 'Horario alternativo'
    professor_excluido_id = request.form.get('professor_excluido_id', type=int)
    periodo_bloqueado = request.form.get('periodo_bloqueado', type=int)
    observacao_partes = []
    if professor_excluido_id:
        professor = next(
            (prof for prof in listar_professores(escola['id'], turno_atual) if prof['id'] == professor_excluido_id),
            None,
        )
        observacao_partes.append(f"Sem {professor['nome'] if professor else 'professor selecionado'}")
    if periodo_bloqueado:
        observacao_partes.append(f"Pulando {periodo_bloqueado} periodo")
    observacao = '; '.join(observacao_partes) or None

    try:
        aulas_geradas = _montar_aulas_alternativas_do_dia(
            escola['id'],
            turno_atual,
            dia,
            turma_id,
            professor_excluido_id,
            periodo_bloqueado,
        )
        if aulas_geradas is None:
            sucesso, msg, aulas_geradas = montar_horario_gerado(
                escola['id'],
                turma_id,
                turno_atual,
                professor_ids_excluidos=[professor_excluido_id] if professor_excluido_id else None,
                slots_bloqueados={(turma_id if turma_id else None, dia, periodo_bloqueado)} if periodo_bloqueado else None,
                permitir_grade_incompleta=bool(professor_excluido_id or periodo_bloqueado),
            )
        else:
            sucesso = bool(aulas_geradas)
            msg = "Horario alternativo montado com base no horario oficial."

        if not sucesso:
            flash(msg, 'error')
        else:
            total = criar_horarios_temporarios_lote(
                escola['id'],
                turno_atual,
                data_inicio,
                data_fim,
                dia,
                titulo,
                aulas_geradas,
                observacao,
            )
            flash(
                f'Horario alternativo gerado para {dia}: {total} aulas temporarias criadas.',
                'success',
            )
    except HorarioTemporarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao gerar horario temporario da escola %s.', escola['id'])
        flash(
            'Nao foi possivel gerar o horario alternativo agora. '
            'Verifique se as aulas, professores e turmas estao consistentes e tente novamente.',
            'error',
        )

    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))
    if turma_id_contexto and turno_atual == request.args.get('turno'):
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id_contexto))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral'))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/limpar', methods=['POST'])
@login_required
def limpar_horarios(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    alvo = request.form.get('limpar_alvo', 'todas')
    limpar_turma_id = None
    if alvo != 'todas':
        try:
            limpar_turma_id = int(alvo)
        except (TypeError, ValueError):
            flash('Selecione uma turma válida para limpar.', 'error')
            return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, view='geral'))
    try:
        limpar_aulas(escola['id'], limpar_turma_id, _active_turno())
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
            _active_turno(),
        )
    except ScheduleConflictError as exc:
        return _json_error(str(exc), code='schedule_conflict')
    except ScheduleValidationError as exc:
        return _json_error(str(exc), code='schedule_validation')
    except (TypeError, ValueError):
        return _json_error('Dados obrigatórios inválidos.', code='invalid_payload')

    return jsonify({'status': 'ok', 'aula_id': aula_id})


@dashboard_bp.route('/escola/<int:escola_id>/horarios/aula/<int:aula_id>/deletar', methods=['POST'])
@login_required
def deletar_aula_manual(escola_id, aula_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule', json_response=True)
    if failure:
        return failure

    try:
        removida = deletar_aula(aula_id, escola_id=escola['id'], turno=_active_turno())
    except Exception:
        current_app.logger.exception('Erro ao remover aula %s da escola %s.', aula_id, escola['id'])
        return _json_error('Nao foi possivel remover a aula agora.', code='delete_failed')

    if not removida:
        return _json_error('Aula nao encontrada.', status_code=404, code='not_found')

    return jsonify({'status': 'ok'})


@dashboard_bp.route('/escola/<int:escola_id>/horarios/temporario', methods=['POST'])
@login_required
def criar_temporario(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    try:
        criar_horario_temporario(
            escola['id'],
            _active_turno(),
            turma_id,
            request.form.get('data_inicio'),
            request.form.get('data_fim') or request.form.get('data_inicio'),
            request.form.get('dia'),
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
        flash('Nao foi possivel criar o horario temporario agora.', 'error')

    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))


@dashboard_bp.route('/escola/<int:escola_id>/horarios/temporario/<int:horario_id>/deletar', methods=['POST'])
@login_required
def deletar_temporario(escola_id, horario_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    try:
        removido = deletar_horario_temporario(horario_id, escola['id'], _active_turno())
        flash('Horario temporario removido.' if removido else 'Horario temporario nao encontrado.', 'success' if removido else 'error')
    except Exception:
        current_app.logger.exception('Erro ao remover horario temporario %s da escola %s.', horario_id, escola['id'])
        flash('Nao foi possivel remover o horario temporario agora.', 'error')

    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id))


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
            f'Horario alternativo removido: {removidos} aula(s).' if removidos else 'Horario alternativo nao encontrado.',
            'success' if removidos else 'error',
        )
    except HorarioTemporarioValidationError as exc:
        flash(str(exc), 'error')
    except Exception:
        current_app.logger.exception('Erro ao remover grupo de horario temporario da escola %s.', escola['id'])
        flash('Nao foi possivel remover o horario alternativo agora.', 'error')

    turma_id = request.form.get('turma_id', type=int)
    if turma_id:
        return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))
    return redirect(_dashboard_url('dashboard.horarios', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/mover_aula', methods=['POST'])
@login_required
def mover(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule', json_response=True)
    if failure:
        return failure

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
    filepath = exportar_pdf(escola, aulas, turmas, disciplinas, color_mode=_export_color_mode())
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
    aulas = _normalizar_aulas_temporarias_para_export(_filtrar_horarios_temporarios_grupo(
        escola['id'],
        turno_atual,
        request.args.get('titulo'),
        request.args.get('data_inicio'),
        request.args.get('data_fim') or request.args.get('data_inicio'),
        request.args.get('dia'),
        request.args.get('observacao'),
    ))
    turmas = listar_turmas(escola['id'], turno_atual)
    turma_ids = {aula['turma_id'] for aula in aulas}
    turmas = [turma for turma in turmas if turma['id'] in turma_ids]
    filepath = exportar_excel(escola, aulas, turmas, color_mode=_export_color_mode())
    return _send_temp_file(filepath, f'horario-alternativo-{turno_atual}.xlsx')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/temporario/pdf')
@login_required
def exportar_temporario_pdf(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas = _normalizar_aulas_temporarias_para_export(_filtrar_horarios_temporarios_grupo(
        escola['id'],
        turno_atual,
        request.args.get('titulo'),
        request.args.get('data_inicio'),
        request.args.get('data_fim') or request.args.get('data_inicio'),
        request.args.get('dia'),
        request.args.get('observacao'),
    ))
    turmas = listar_turmas(escola['id'], turno_atual)
    turma_ids = {aula['turma_id'] for aula in aulas}
    turmas = [turma for turma in turmas if turma['id'] in turma_ids]
    disciplinas = listar_disciplinas(escola['id'], turno_atual)
    filepath = exportar_pdf(escola, aulas, turmas, disciplinas, color_mode=_export_color_mode())
    return _send_temp_file(filepath, f'horario-alternativo-{turno_atual}.pdf')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/temporario/pdf/geral')
@login_required
def exportar_temporario_pdf_geral(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    turno_atual = _active_turno()
    aulas = _normalizar_aulas_temporarias_para_export(_filtrar_horarios_temporarios_grupo(
        escola['id'],
        turno_atual,
        request.args.get('titulo'),
        request.args.get('data_inicio'),
        request.args.get('data_fim') or request.args.get('data_inicio'),
        request.args.get('dia'),
        request.args.get('observacao'),
    ))
    turmas = listar_turmas(escola['id'], turno_atual)
    turma_ids = {aula['turma_id'] for aula in aulas}
    turmas = [turma for turma in turmas if turma['id'] in turma_ids]
    filepath = exportar_pdf_matriz(escola, aulas, turmas, color_mode=_export_color_mode())
    return _send_temp_file(filepath, f'horario-alternativo-geral-{turno_atual}.pdf')
