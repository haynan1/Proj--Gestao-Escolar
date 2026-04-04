from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.escola import criar_escola, listar_escolas, buscar_escola, deletar_escola

escola_bp = Blueprint('escola', __name__)


@escola_bp.route('/')
def home():
    escolas = listar_escolas()
    return render_template('home.html', escolas=escolas)


@escola_bp.route('/escola/criar', methods=['POST'])
def criar():
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('O nome da escola é obrigatório.', 'error')
        return redirect(url_for('escola.home'))
    sucesso, msg = criar_escola(nome)
    flash(msg, 'success' if sucesso else 'error')
    return redirect(url_for('escola.home'))


@escola_bp.route('/escola/<int:escola_id>/deletar', methods=['POST'])
def deletar(escola_id):
    deletar_escola(escola_id)
    flash('Escola removida com sucesso.', 'success')
    return redirect(url_for('escola.home'))
