from functools import wraps

from flask import flash, g, jsonify, redirect, request, url_for


ROLE_ADMIN = 'administrador'
ROLE_COORDINATOR = 'coordenador'
ROLE_STAFF = 'funcionario'
SCHEDULE_MANAGER_ROLES = {ROLE_ADMIN, ROLE_COORDINATOR}

ROLE_LABELS = {
    ROLE_ADMIN: 'Administrador',
    ROLE_COORDINATOR: 'Coordenador',
    ROLE_STAFF: 'Funcionario',
}

ROLE_PERMISSIONS = {
    ROLE_ADMIN: {
        'admin_access',
        'manage_users',
        'manage_links',
        'manage_schools',
        'manage_school_resources',
        'manage_schedule',
        'view_school',
        'export_school',
    },
    ROLE_COORDINATOR: {
        'manage_school_resources',
        'manage_schedule',
        'view_school',
        'export_school',
    },
    ROLE_STAFF: {
        'view_school',
        'export_school',
    },
}


def normalize_role(role: str | None) -> str:
    if not role:
        return ROLE_STAFF
    role = role.strip().lower()
    if role in ROLE_PERMISSIONS:
        return role
    return ROLE_STAFF


def get_role_label(role: str | None) -> str:
    return ROLE_LABELS.get(normalize_role(role), ROLE_LABELS[ROLE_STAFF])


def user_has_permission(user: dict | None, permission: str) -> bool:
    if not user:
        return False
    role = normalize_role(user.get('role'))
    if permission == 'manage_schedule' and role not in SCHEDULE_MANAGER_ROLES:
        return False
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission: str):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not user_has_permission(g.get('user'), permission):
                flash('Voce nao tem permissao para acessar esse recurso.', 'error')
                return redirect(url_for('escola.home'))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def forbid_without_school_permission(permission: str):
    if user_has_permission(g.get('user'), permission):
        return None

    if request.is_json:
        response = jsonify({
            'status': 'erro',
            'error': {
                'code': 'forbidden',
                'message': 'Voce nao tem permissao para executar esta acao.',
            },
        })
        response.status_code = 403
        return response

    flash('Voce nao tem permissao para executar esta acao.', 'error')
    return redirect(url_for('escola.home'))
