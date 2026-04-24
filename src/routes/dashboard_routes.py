import os

from flask import (
    Blueprint,
    after_this_request,
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
from exports.pdf_export import exportar_pdf
from models.aula import (
    ScheduleConflictError,
    ScheduleValidationError,
    listar_aulas,
    mover_aula,
)
from models.disciplina import (
    DisciplineInUseError,
    atualizar_disciplina,
    criar_disciplina,
    deletar_disciplina,
    listar_disciplinas,
)
from models.escola import buscar_escola
from models.professor import (
    atualizar_professor,
    criar_professor,
    deletar_professor,
    listar_professores,
)
from models.turma import atualizar_turma, criar_turma, deletar_turma, listar_turmas
from scheduler import gerar_horario
from utils.conflitos import PERIODOS


dashboard_bp = Blueprint('dashboard', __name__)

DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']


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


def _load_accessible_escola(escola_id):
    return buscar_escola(escola_id, user=g.user)


def _guard_school(escola_id, permission='view_school', json_response=False):
    escola = _load_accessible_escola(escola_id)
    if not escola:
        if json_response:
            return None, _json_error('Escola nao encontrada.', status_code=404, code='school_not_found')
        flash('Escola nao encontrada.', 'error')
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

    disciplinas = listar_disciplinas(escola_id)
    professores = listar_professores(escola_id)
    turmas = listar_turmas(escola_id)
    return render_template(
        'dashboard.html',
        escola=escola,
        disciplinas=disciplinas,
        professores=professores,
        turmas=turmas,
        dias_semana=DIAS_SEMANA,
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
        flash('Nome da disciplina e obrigatorio.', 'error')
    else:
        sucesso, msg = criar_disciplina(escola['id'], nome, cor)
        flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


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
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


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
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/professor/criar', methods=['POST'])
@login_required
def criar_prof(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    disciplina_id = request.form.get('disciplina_id')
    max_aulas = request.form.get('max_aulas_semana', 10)
    dias = request.form.getlist('dias_disponiveis')
    turma_ids = request.form.getlist('turma_ids')
    if not nome or not disciplina_id:
        flash('Nome e disciplina sao obrigatorios.', 'error')
    elif not dias:
        flash('Selecione pelo menos um dia disponivel.', 'error')
    elif not turma_ids:
        flash('Selecione pelo menos uma turma para vincular ao professor.', 'error')
    else:
        sucesso, msg = criar_professor(escola['id'], nome, int(disciplina_id), int(max_aulas), dias, turma_ids)
        flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/editar', methods=['POST'])
@login_required
def editar_prof(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    disciplina_id = request.form.get('disciplina_id')
    max_aulas = request.form.get('max_aulas_semana', 10)
    dias = request.form.getlist('dias_disponiveis')
    turma_ids = request.form.getlist('turma_ids')
    if nome and disciplina_id and dias and turma_ids:
        atualizar_professor(prof_id, escola['id'], nome, int(disciplina_id), int(max_aulas), dias, turma_ids)
        flash('Professor atualizado.', 'success')
    else:
        flash('Preencha nome, disciplina, dias disponiveis e pelo menos uma turma.', 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/deletar', methods=['POST'])
@login_required
def deletar_prof(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    deletar_professor(prof_id, escola['id'])
    flash('Professor removido.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/criar', methods=['POST'])
@login_required
def criar_turm(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome da turma e obrigatorio.', 'error')
    else:
        sucesso, msg = criar_turma(escola['id'], nome)
        flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/editar', methods=['POST'])
@login_required
def editar_turm(escola_id, turma_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    nome = request.form.get('nome', '').strip()
    if nome:
        atualizar_turma(turma_id, escola['id'], nome)
        flash('Turma atualizada.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/deletar', methods=['POST'])
@login_required
def deletar_turm(escola_id, turma_id):
    escola, failure = _guard_school(escola_id, permission='manage_school_resources')
    if failure:
        return failure

    deletar_turma(turma_id, escola['id'])
    flash('Turma removida.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/horarios')
@login_required
def horarios(escola_id):
    escola, failure = _guard_school(escola_id, permission='view_school')
    if failure:
        return failure

    turmas = listar_turmas(escola['id'])
    aulas = listar_aulas(escola['id'])
    disciplinas = listar_disciplinas(escola['id'])
    professores = listar_professores(escola['id'])

    grade = {}
    for turma in turmas:
        grade[turma['id']] = {dia: {p: None for p in PERIODOS} for dia in DIAS_SEMANA}

    for aula in aulas:
        tid = aula['turma_id']
        dia = aula['dia']
        per = aula['periodo']
        if tid in grade and dia in grade[tid]:
            grade[tid][dia][per] = aula

    turma_selecionada_id = request.args.get('turma_id', type=int)
    if not turma_selecionada_id and turmas:
        turma_selecionada_id = turmas[0]['id']

    return render_template(
        'horarios.html',
        escola=escola,
        turmas=turmas,
        grade=grade,
        aulas=aulas,
        disciplinas=disciplinas,
        professores=professores,
        dias=DIAS_SEMANA,
        periodos=PERIODOS,
        turma_selecionada_id=turma_selecionada_id,
    )


@dashboard_bp.route('/escola/<int:escola_id>/gerar', methods=['POST'])
@login_required
def gerar(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule')
    if failure:
        return failure

    turma_id = request.form.get('turma_id', type=int)
    sucesso, msg, total = gerar_horario(escola['id'], turma_id)
    flash(msg, 'success' if sucesso else 'error')
    if turma_id:
        return redirect(url_for('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))
    return redirect(url_for('dashboard.horarios', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/mover_aula', methods=['POST'])
@login_required
def mover(escola_id):
    escola, failure = _guard_school(escola_id, permission='manage_schedule', json_response=True)
    if failure:
        return failure

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error('Corpo da requisicao invalido.', code='invalid_payload')

    aula_id = data.get('aula_id')
    novo_dia = data.get('dia')
    novo_periodo = data.get('periodo')

    if aula_id is None or novo_dia is None or novo_periodo is None:
        return _json_error('Dados obrigatorios ausentes.', code='invalid_payload')

    try:
        mover_aula(int(aula_id), str(novo_dia), int(novo_periodo), escola_id=escola['id'])
    except ScheduleConflictError as exc:
        return _json_error(str(exc), code='schedule_conflict')
    except ScheduleValidationError as exc:
        return _json_error(str(exc), code='schedule_validation')
    except ValueError:
        return _json_error('IDs e periodos devem ser numericos.', code='invalid_payload')

    return jsonify({'status': 'ok'})


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/ocupacao')
@login_required
def ocupacao_professor(escola_id, prof_id):
    escola, failure = _guard_school(escola_id, permission='view_school', json_response=True)
    if failure:
        return failure

    aulas = listar_aulas(escola['id'])
    ocupacao = []
    for aula in aulas:
        if aula['professor_id'] == prof_id:
            ocupacao.append({
                'dia': aula['dia'],
                'periodo': aula['periodo'],
                'turma_id': aula['turma_id'],
                'turma_nome': aula['turma_nome'],
            })
    return jsonify(ocupacao)


@dashboard_bp.route('/escola/<int:escola_id>/exportar/excel')
@login_required
def exportar_xls(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    aulas = listar_aulas(escola['id'])
    turmas = listar_turmas(escola['id'])
    filepath = exportar_excel(escola, aulas, turmas)
    return _send_temp_file(filepath, 'horario.xlsx')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/pdf')
@login_required
def exportar_pdf_route(escola_id):
    escola, failure = _guard_school(escola_id, permission='export_school')
    if failure:
        return failure

    aulas = listar_aulas(escola['id'])
    turmas = listar_turmas(escola['id'])
    disciplinas = listar_disciplinas(escola['id'])
    filepath = exportar_pdf(escola, aulas, turmas, disciplinas)
    return _send_temp_file(filepath, 'horario.pdf')
