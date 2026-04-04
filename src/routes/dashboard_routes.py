import os

from flask import (
    Blueprint,
    after_this_request,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from models.escola import buscar_escola
from models.disciplina import (
    DisciplineInUseError,
    atualizar_disciplina,
    criar_disciplina,
    deletar_disciplina,
    listar_disciplinas,
)
from models.professor import (
    atualizar_professor,
    criar_professor,
    deletar_professor,
    listar_professores,
)
from models.turma import criar_turma, listar_turmas, atualizar_turma, deletar_turma
from models.aula import (
    ScheduleConflictError,
    ScheduleValidationError,
    listar_aulas,
    mover_aula,
)
from scheduler import gerar_horario
from exports.excel_export import exportar_excel
from exports.pdf_export import exportar_pdf
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


@dashboard_bp.route('/escola/<int:escola_id>/dashboard')
def dashboard(escola_id):
    escola = buscar_escola(escola_id)
    if not escola:
        flash('Escola não encontrada.', 'error')
        return redirect(url_for('escola.home'))
    disciplinas = listar_disciplinas(escola_id)
    professores = listar_professores(escola_id)
    turmas = listar_turmas(escola_id)
    return render_template('dashboard.html',
                           escola=escola,
                           disciplinas=disciplinas,
                           professores=professores,
                           turmas=turmas,
                           dias_semana=DIAS_SEMANA)


# ─── Disciplinas ────────────────────────────────────────────────────────────────

@dashboard_bp.route('/escola/<int:escola_id>/disciplina/criar', methods=['POST'])
def criar_disc(escola_id):
    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#22c55e').strip()
    if not nome:
        flash('Nome da disciplina é obrigatório.', 'error')
    else:
        sucesso, msg = criar_disciplina(escola_id, nome, cor)
        flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/disciplina/<int:disc_id>/editar', methods=['POST'])
def editar_disc(escola_id, disc_id):
    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#22c55e').strip()
    if nome:
        atualizar_disciplina(disc_id, nome, cor)
        flash('Disciplina atualizada.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/disciplina/<int:disc_id>/deletar', methods=['POST'])
def deletar_disc(escola_id, disc_id):
    try:
        deletar_disciplina(disc_id)
        flash('Disciplina removida.', 'success')
    except DisciplineInUseError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


# ─── Professores ────────────────────────────────────────────────────────────────

@dashboard_bp.route('/escola/<int:escola_id>/professor/criar', methods=['POST'])
def criar_prof(escola_id):
    nome = request.form.get('nome', '').strip()
    disciplina_id = request.form.get('disciplina_id')
    max_aulas = request.form.get('max_aulas_semana', 10)
    dias = request.form.getlist('dias_disponiveis')
    if not nome or not disciplina_id:
        flash('Nome e disciplina são obrigatórios.', 'error')
    elif not dias:
        flash('Selecione pelo menos um dia disponível.', 'error')
    else:
        sucesso, msg = criar_professor(escola_id, nome, int(disciplina_id), int(max_aulas), dias)
        flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/editar', methods=['POST'])
def editar_prof(escola_id, prof_id):
    nome = request.form.get('nome', '').strip()
    disciplina_id = request.form.get('disciplina_id')
    max_aulas = request.form.get('max_aulas_semana', 10)
    dias = request.form.getlist('dias_disponiveis')
    if nome and disciplina_id and dias:
        atualizar_professor(prof_id, nome, int(disciplina_id), int(max_aulas), dias)
        flash('Professor atualizado.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/deletar', methods=['POST'])
def deletar_prof(escola_id, prof_id):
    deletar_professor(prof_id)
    flash('Professor removido.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


# ─── Turmas ─────────────────────────────────────────────────────────────────────

@dashboard_bp.route('/escola/<int:escola_id>/turma/criar', methods=['POST'])
def criar_turm(escola_id):
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome da turma é obrigatório.', 'error')
    else:
        sucesso, msg = criar_turma(escola_id, nome)
        flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/editar', methods=['POST'])
def editar_turm(escola_id, turma_id):
    nome = request.form.get('nome', '').strip()
    if nome:
        atualizar_turma(turma_id, nome)
        flash('Turma atualizada.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


@dashboard_bp.route('/escola/<int:escola_id>/turma/<int:turma_id>/deletar', methods=['POST'])
def deletar_turm(escola_id, turma_id):
    deletar_turma(turma_id)
    flash('Turma removida.', 'success')
    return redirect(url_for('dashboard.dashboard', escola_id=escola_id))


# ─── Horários ───────────────────────────────────────────────────────────────────

@dashboard_bp.route('/escola/<int:escola_id>/horarios')
def horarios(escola_id):
    escola = buscar_escola(escola_id)
    if not escola:
        flash('Escola não encontrada.', 'error')
        return redirect(url_for('escola.home'))
    turmas = listar_turmas(escola_id)
    aulas = listar_aulas(escola_id)
    disciplinas = listar_disciplinas(escola_id)
    professores = listar_professores(escola_id)

    # Organiza aulas por turma -> dia -> periodo
    grade = {}
    for turma in turmas:
        grade[turma['id']] = {
            dia: {p: None for p in PERIODOS}
            for dia in DIAS_SEMANA
        }

    for aula in aulas:
        tid = aula['turma_id']
        dia = aula['dia']
        per = aula['periodo']
        if tid in grade and dia in grade[tid]:
            grade[tid][dia][per] = aula

    turma_selecionada_id = request.args.get('turma_id', type=int)
    if not turma_selecionada_id and turmas:
        turma_selecionada_id = turmas[0]['id']

    return render_template('horarios.html',
                           escola=escola,
                           turmas=turmas,
                           grade=grade,
                           aulas=aulas,
                           disciplinas=disciplinas,
                           professores=professores,
                           dias=DIAS_SEMANA,
                           periodos=PERIODOS,
                           turma_selecionada_id=turma_selecionada_id)


@dashboard_bp.route('/escola/<int:escola_id>/gerar', methods=['POST'])
def gerar(escola_id):
    turma_id = request.form.get('turma_id', type=int)
    sucesso, msg, total = gerar_horario(escola_id, turma_id)
    flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('dashboard.horarios', escola_id=escola_id, turma_id=turma_id))


@dashboard_bp.route('/escola/<int:escola_id>/mover_aula', methods=['POST'])
def mover(escola_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error('Corpo da requisição inválido.', code='invalid_payload')

    aula_id = data.get('aula_id')
    novo_dia = data.get('dia')
    novo_periodo = data.get('periodo')

    if aula_id is None or novo_dia is None or novo_periodo is None:
        return _json_error('Dados obrigatórios ausentes.', code='invalid_payload')

    try:
        mover_aula(int(aula_id), str(novo_dia), int(novo_periodo), escola_id=escola_id)
    except ScheduleConflictError as exc:
        return _json_error(str(exc), code='schedule_conflict')
    except ScheduleValidationError as exc:
        return _json_error(str(exc), code='schedule_validation')
    except ValueError:
        return _json_error('IDs e períodos devem ser numéricos.', code='invalid_payload')

    return jsonify({'status': 'ok'})


@dashboard_bp.route('/escola/<int:escola_id>/professor/<int:prof_id>/ocupacao')
def ocupacao_professor(escola_id, prof_id):
    """Retorna todos os horários em que o professor já está ocupado em outras turmas."""
    aulas = listar_aulas(escola_id)
    ocupacao = []
    for a in aulas:
        if a['professor_id'] == prof_id:
            ocupacao.append({
                'dia': a['dia'],
                'periodo': a['periodo'],
                'turma_id': a['turma_id'],
                'turma_nome': a['turma_nome']
            })
    return jsonify(ocupacao)


@dashboard_bp.route('/escola/<int:escola_id>/exportar/excel')
def exportar_xls(escola_id):
    escola = buscar_escola(escola_id)
    aulas = listar_aulas(escola_id)
    turmas = listar_turmas(escola_id)
    filepath = exportar_excel(escola, aulas, turmas)
    return _send_temp_file(filepath, 'horario.xlsx')


@dashboard_bp.route('/escola/<int:escola_id>/exportar/pdf')
def exportar_pdf_route(escola_id):
    escola = buscar_escola(escola_id)
    aulas = listar_aulas(escola_id)
    turmas = listar_turmas(escola_id)
    disciplinas = listar_disciplinas(escola_id)
    filepath = exportar_pdf(escola, aulas, turmas, disciplinas)
    return _send_temp_file(filepath, 'horario.pdf')
