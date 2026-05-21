import pytest
from access_control import (
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_STAFF,
    get_role_label,
    normalize_role,
    user_has_permission,
)


class TestNormalizeRole:
    def test_valid_admin(self):
        assert normalize_role('administrador') == ROLE_ADMIN

    def test_valid_coordinator(self):
        assert normalize_role('coordenador') == ROLE_COORDINATOR

    def test_valid_staff(self):
        assert normalize_role('funcionario') == ROLE_STAFF

    def test_unknown_defaults_to_staff(self):
        assert normalize_role('hacker') == ROLE_STAFF

    def test_none_defaults_to_staff(self):
        assert normalize_role(None) == ROLE_STAFF

    def test_empty_string_defaults_to_staff(self):
        assert normalize_role('') == ROLE_STAFF

    def test_case_insensitive(self):
        assert normalize_role('ADMINISTRADOR') == ROLE_ADMIN
        assert normalize_role('Coordenador') == ROLE_COORDINATOR

    def test_strips_whitespace(self):
        assert normalize_role('  administrador  ') == ROLE_ADMIN


class TestUserHasPermission:
    def test_none_user_has_no_permissions(self):
        assert not user_has_permission(None, 'view_school')
        assert not user_has_permission(None, 'admin_access')

    def test_admin_has_all_permissions(self):
        user = {'role': ROLE_ADMIN}
        for perm in ('admin_access', 'manage_users', 'manage_links', 'manage_schools',
                     'manage_reports', 'manage_school_resources', 'manage_schedule',
                     'view_school', 'export_school'):
            assert user_has_permission(user, perm), f"Admin should have {perm}"

    def test_coordinator_has_schedule_permission(self):
        user = {'role': ROLE_COORDINATOR}
        assert user_has_permission(user, 'manage_schedule')

    def test_coordinator_lacks_admin_permissions(self):
        user = {'role': ROLE_COORDINATOR}
        assert not user_has_permission(user, 'admin_access')
        assert not user_has_permission(user, 'manage_users')

    def test_staff_has_view_and_export(self):
        user = {'role': ROLE_STAFF}
        assert user_has_permission(user, 'view_school')
        assert user_has_permission(user, 'export_school')

    def test_staff_lacks_management_permissions(self):
        user = {'role': ROLE_STAFF}
        for perm in ('admin_access', 'manage_users', 'manage_schedule',
                     'manage_school_resources', 'manage_reports'):
            assert not user_has_permission(user, perm), f"Staff should NOT have {perm}"

    def test_unknown_role_has_no_management_permissions(self):
        user = {'role': 'desconhecido'}
        assert not user_has_permission(user, 'manage_schedule')

    def test_schedule_requires_admin_or_coordinator(self):
        assert not user_has_permission({'role': ROLE_STAFF}, 'manage_schedule')
        assert user_has_permission({'role': ROLE_COORDINATOR}, 'manage_schedule')
        assert user_has_permission({'role': ROLE_ADMIN}, 'manage_schedule')


class TestGetRoleLabel:
    def test_admin_label(self):
        assert get_role_label(ROLE_ADMIN) == 'Administrador'

    def test_coordinator_label(self):
        assert get_role_label(ROLE_COORDINATOR) == 'Coordenador'

    def test_staff_label(self):
        assert get_role_label(ROLE_STAFF) == 'Funcionario'

    def test_unknown_defaults_to_staff_label(self):
        assert get_role_label('qualquer') == 'Funcionario'

    def test_none_defaults_to_staff_label(self):
        assert get_role_label(None) == 'Funcionario'
