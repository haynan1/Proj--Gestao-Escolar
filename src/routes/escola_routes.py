from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from auth import login_required
from models.escola import criar_escola, deletar_escola, listar_escolas

escola_bp = Blueprint('escola', __name__)


@escola_bp.route('/')
@login_required
def home():
    escolas = listar_escolas(g.user['id'])
    return render_template('home.html', escolas=escolas)


@escola_bp.route('/escola/criar', methods=['POST'])
@login_required
def criar():
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('O nome da escola é obrigatório.', 'error')
        return redirect(url_for('escola.home'))
    sucesso, msg = criar_escola(g.user['id'], nome)
    flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('escola.home'))


@escola_bp.route('/escola/<int:escola_id>/deletar', methods=['POST'])
@login_required
def deletar(escola_id):
    deletar_escola(escola_id, g.user['id'])
    flash('Escola removida com sucesso.', 'success')
    return redirect(url_for('escola.home'))
