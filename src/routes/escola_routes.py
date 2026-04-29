from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from access_control import user_has_permission
from auth import login_required
from models.escola import (
    criar_escola,
    deletar_escola,
    duplicar_escola_oculta,
    listar_escolas_para_usuario,
)

escola_bp = Blueprint('escola', __name__)


@escola_bp.route('/')
@login_required
def home():
    escolas = listar_escolas_para_usuario(g.user)
    return render_template('home.html', escolas=escolas)


@escola_bp.route('/escola/criar', methods=['POST'])
@login_required
def criar():
    if not user_has_permission(g.user, 'manage_schools'):
        flash('Voce nao tem permissao para criar escolas.', 'error')
        return redirect(url_for('escola.home'))

    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('O nome da escola e obrigatorio.', 'error')
        return redirect(url_for('escola.home'))
    sucesso, msg = criar_escola(g.user['id'], nome)
    flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('escola.home'))


@escola_bp.route('/escola/<int:escola_id>/deletar', methods=['POST'])
@login_required
def deletar(escola_id):
    if not user_has_permission(g.user, 'manage_schools'):
        flash('Voce nao tem permissao para remover escolas.', 'error')
        return redirect(url_for('escola.home'))

    deletar_escola(escola_id)
    flash('Escola removida com sucesso.', 'success')
    return redirect(url_for('escola.home'))


@escola_bp.route('/escola/<int:escola_id>/backup', methods=['POST'])
@login_required
def criar_backup(escola_id):
    if not user_has_permission(g.user, 'admin_access'):
        flash('Apenas administradores podem criar backups ocultos de escolas.', 'error')
        return redirect(url_for('escola.home'))

    sucesso, msg, _backup_id = duplicar_escola_oculta(escola_id)
    flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('escola.home'))
