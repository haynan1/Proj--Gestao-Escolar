import pytest
from unittest.mock import MagicMock, patch


class TestIsafeRedirectTarget:
    """Tests for auth._is_safe_redirect_target."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from auth import _is_safe_redirect_target
        self.is_safe = _is_safe_redirect_target

    def test_relative_path_is_safe(self):
        assert self.is_safe('/dashboard')
        assert self.is_safe('/escola/1/horarios')

    def test_absolute_url_is_unsafe(self):
        assert not self.is_safe('http://evil.com/steal')
        assert not self.is_safe('https://attacker.io/')

    def test_protocol_relative_is_unsafe(self):
        assert not self.is_safe('//evil.com')

    def test_empty_string_is_unsafe(self):
        assert not self.is_safe('')

    def test_path_without_leading_slash_is_unsafe(self):
        assert not self.is_safe('dashboard')


class TestGenerateCsrfToken:
    """CSRF token generation should be idempotent per session."""

    def test_token_generated_once_per_session(self, app):
        with app.test_request_context('/'):
            from flask import session
            from auth import generate_csrf_token, CSRF_SESSION_KEY

            token1 = generate_csrf_token()
            token2 = generate_csrf_token()

            assert token1 == token2
            assert session.get(CSRF_SESSION_KEY) == token1

    def test_token_has_sufficient_entropy(self, app):
        with app.test_request_context('/'):
            from auth import generate_csrf_token

            token = generate_csrf_token()
            # URL-safe base64 of 32 bytes is at minimum 43 characters
            assert len(token) >= 43


class TestCsrfProtect:
    """CSRF middleware should block unsafe methods without a valid token."""

    def test_get_request_bypasses_csrf(self, client, app):
        with patch('models.user.buscar_usuario_por_id', return_value=None):
            response = client.get('/login')
        assert response.status_code == 200

    def test_post_without_token_returns_400_for_json(self, client):
        response = client.post(
            '/login',
            json={'email': 'a@b.com', 'senha': 'test'},
            content_type='application/json',
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error']['code'] == 'csrf_invalid'

    def test_post_without_token_redirects_for_form(self, client):
        response = client.post('/login', data={'email': 'a@b.com', 'senha': 'test'})
        # Redirected back, not 200 with form content
        assert response.status_code in (302, 400)
