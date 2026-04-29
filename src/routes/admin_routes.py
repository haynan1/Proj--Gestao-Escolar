import re

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from access_control import ROLE_ADMIN, ROLE_COORDINATOR, ROLE_STAFF, require_permission
from auth import login_required
from models.escola import deletar_backup_oculto, listar_backups_ocultos, listar_escolas
from models.user import (
    atualizar_role_usuario,
    buscar_usuario_por_id,
    criar_usuario,
    deletar_usuario,
    is_master_user,
    listar_usuarios,
)
from models.user_link import criar_vinculo_usuario_escola, deletar_vinculo, listar_vinculos


EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
MANAGED_ROLE_OPTIONS = [ROLE_ADMIN, ROLE_COORDINATOR, ROLE_STAFF]

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/usuarios')
@login_required
@require_permission('manage_users')
def usuarios():
    usuarios = listar_usuarios()
    return render_template(
        'admin_users.html',
        usuarios=usuarios,
        escolas=listar_escolas(),
        vinculos=listar_vinculos(),
        role_options=MANAGED_ROLE_OPTIONS,
        master_user_email=next((usuario['email'] for usuario in usuarios if is_master_user(usuario)), ''),
    )


@admin_bp.route('/backups')
@login_required
@require_permission('admin_access')
def backups():
    return render_template('admin_backups.html', backups=listar_backups_ocultos())


@admin_bp.route('/backups/<int:escola_id>/deletar', methods=['POST'])
@login_required
@require_permission('admin_access')
def deletar_backup(escola_id):
    if deletar_backup_oculto(escola_id):
        flash('Backup oculto excluido com sucesso.', 'success')
    else:
        flash('Backup oculto nao encontrado.', 'error')
    return redirect(url_for('admin.backups'))


@admin_bp.route('/usuarios/criar', methods=['POST'])
@login_required
@require_permission('manage_users')
def criar_usuario_route():
    nome = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    role = request.form.get('role', ROLE_STAFF).strip().lower()

    if not nome or not email or not senha:
        flash('Preencha nome, e-mail, senha e perfil.', 'error')
    elif not EMAIL_PATTERN.match(email):
        flash('Informe um e-mail valido.', 'error')
    elif len(senha) < 8:
        flash('A senha precisa ter pelo menos 8 caracteres.', 'error')
    else:
        sucesso, mensagem = criar_usuario(
            nome,
            email,
            senha,
            role=role,
            email_verificado=True,
        )
        flash(mensagem, 'success' if sucesso else 'error')

    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/usuarios/<int:usuario_id>/perfil', methods=['POST'])
@login_required
@require_permission('manage_users')
def atualizar_perfil(usuario_id):
    usuario = buscar_usuario_por_id(usuario_id)
    if is_master_user(usuario):
        flash('O usuario master sempre permanece com controle total e nao pode ter o perfil alterado.', 'error')
        return redirect(url_for('admin.usuarios'))

    role = request.form.get('role', '').strip().lower()
    if usuario_id == g.user['id'] and role != ROLE_ADMIN:
        flash('O administrador logado nao pode remover o proprio acesso administrativo aqui.', 'error')
        return redirect(url_for('admin.usuarios'))

    try:
        atualizar_role_usuario(usuario_id, role)
        flash('Perfil atualizado com sucesso.', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/usuarios/<int:usuario_id>/deletar', methods=['POST'])
@login_required
@require_permission('manage_users')
def deletar_usuario_route(usuario_id):
    usuario = buscar_usuario_por_id(usuario_id)
    if is_master_user(usuario):
        flash('O usuario master nao pode ser excluido.', 'error')
        return redirect(url_for('admin.usuarios'))

    if usuario_id == g.user['id']:
        flash('Voce nao pode excluir o usuario que esta logado.', 'error')
        return redirect(url_for('admin.usuarios'))

    deletar_usuario(usuario_id)
    flash('Usuario removido com sucesso.', 'success')
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/vinculos/criar', methods=['POST'])
@login_required
@require_permission('manage_links')
def criar_vinculo():
    usuario_id = request.form.get('usuario_id', type=int)
    escola_id = request.form.get('escola_id', type=int)
    if not usuario_id or not escola_id:
        flash('Selecione usuario e escola para criar o vinculo.', 'error')
    elif is_master_user(buscar_usuario_por_id(usuario_id)):
        flash('O usuario master nao precisa de ajustes de vinculo pela interface.', 'error')
    else:
        sucesso, mensagem = criar_vinculo_usuario_escola(usuario_id, escola_id)
        flash(mensagem, 'success' if sucesso else 'error')
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/vinculos/<int:vinculo_id>/deletar', methods=['POST'])
@login_required
@require_permission('manage_links')
def deletar_vinculo_route(vinculo_id):
    vinculo = next((item for item in listar_vinculos() if item['id'] == vinculo_id), None)
    if vinculo and is_master_user({'email': vinculo.get('usuario_email')}):
        flash('O vinculo do usuario master nao pode ser alterado por esta tela.', 'error')
    else:
        deletar_vinculo(vinculo_id)
        flash('Vinculo removido com sucesso.', 'success')
    return redirect(url_for('admin.usuarios'))
