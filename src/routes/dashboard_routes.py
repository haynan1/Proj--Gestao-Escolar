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
from scheduler import gerar_horario


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
