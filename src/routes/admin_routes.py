import io
import re
from datetime import datetime

from flask import Blueprint, Response, flash, g, redirect, render_template, request, url_for

from access_control import ROLE_ADMIN, ROLE_COORDINATOR, ROLE_STAFF, require_permission
from auth import login_required
from database.connection import get_connection
from models.escola import (
    deletar_backup_oculto,
    listar_backups_ocultos,
    listar_escolas,
    recriar_backup_oculto,
    restaurar_backup_oculto,
)
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


@admin_bp.route('/exportar-banco')
@login_required
@require_permission('admin_access')
def exportar_banco():
    """Gera e faz download de um dump SQL completo do banco de dados."""
    try:
        sql = _gerar_dump_sql()
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Erro ao gerar dump do banco.')
        flash('Nao foi possivel gerar o dump do banco. Verifique os logs.', 'error')
        return redirect(url_for('admin.backups'))

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'flowter_dump_{timestamp}.sql'
    return Response(
        sql,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def _gerar_dump_sql():
    """
    Gera dump SQL completo do banco usando mysql-connector (sem mysqldump).
    Retorna uma string com todo o SQL pronto para importar em outro MySQL.
    """
    conn = get_connection()
    out = io.StringIO()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    out.write(f'-- Flowter Database Dump\n')
    out.write(f'-- Gerado em: {now}\n')
    out.write(f'-- Uso: importar em MySQL/MariaDB local via: mysql -u root -p nome_banco < arquivo.sql\n')
    out.write('--\n\n')
    out.write('SET FOREIGN_KEY_CHECKS = 0;\n')
    out.write('SET NAMES utf8mb4;\n')
    out.write('SET CHARACTER SET utf8mb4;\n\n')

    try:
        tables = [
            row['Tables_in_' + _get_db_name(conn)] if _get_db_name(conn) else list(row.values())[0]
            for row in conn.execute('SHOW TABLES').fetchall()
        ]

        for table in tables:
            # DDL
            ddl_row = conn.execute(f'SHOW CREATE TABLE `{table}`').fetchone()
            create_sql = ddl_row['Create Table'] if ddl_row else ''
            out.write(f'DROP TABLE IF EXISTS `{table}`;\n')
            out.write(create_sql + ';\n\n')

            # Dados
            rows = conn.execute(f'SELECT * FROM `{table}`').fetchall()
            if rows:
                cols = ', '.join(f'`{c}`' for c in rows[0].keys())
                out.write(f'INSERT INTO `{table}` ({cols}) VALUES\n')
                value_lines = []
                for row in rows:
                    vals = ', '.join(_sql_value(v) for v in row.values())
                    value_lines.append(f'  ({vals})')
                out.write(',\n'.join(value_lines))
                out.write(';\n\n')

        out.write('SET FOREIGN_KEY_CHECKS = 1;\n')
    finally:
        conn.close()

    return out.getvalue()


def _get_db_name(conn):
    row = conn.execute('SELECT DATABASE() AS db').fetchone()
    return row['db'] if row else ''


def _sql_value(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (bytes, bytearray)):
        return '0x' + value.hex()
    # datetime, date, str e qualquer outro → string escapada
    s = str(value)
    s = s.replace('\\', '\\\\').replace("'", "\\'").replace('\0', '\\0')
    s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\x1a', '\\Z')
    return f"'{s}'"


@admin_bp.route('/backups/<int:escola_id>/restaurar', methods=['POST'])
@login_required
@require_permission('admin_access')
def restaurar_backup(escola_id):
    sucesso, mensagem, escola_restaurada_id = restaurar_backup_oculto(escola_id)
    flash(mensagem, 'success' if sucesso else 'error')
    if sucesso and escola_restaurada_id:
        return redirect(url_for('admin.usuarios'))
    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<int:escola_id>/deletar', methods=['POST'])
@login_required
@require_permission('admin_access')
def deletar_backup(escola_id):
    if deletar_backup_oculto(escola_id):
        flash('Backup oculto excluido com sucesso.', 'success')
    else:
        flash('Backup oculto nao encontrado.', 'error')
    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<int:escola_id>/recriar', methods=['POST'])
@login_required
@require_permission('admin_access')
def recriar_backup(escola_id):
    sucesso, mensagem, _novo_backup_id = recriar_backup_oculto(escola_id)
    flash(mensagem, 'success' if sucesso else 'error')
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
