import os
import sys
import types
from unittest.mock import MagicMock

import pytest

# Add src to path before any project imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Required env vars before importing anything that reads them
os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret-key-ci-not-for-production')
os.environ.setdefault('DB_HOST', '127.0.0.1')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_NAME', 'test_gestao')
os.environ.setdefault('APP_BASE_URL', '')
os.environ.setdefault('ENABLE_TEST_USER', '0')


def _make_cursor(row=None, rows=None):
    c = MagicMock()
    c.fetchone.return_value = row
    c.fetchall.return_value = rows if rows is not None else []
    c.lastrowid = 1
    c.rowcount = 0
    return c


def make_mock_conn(row=None, rows=None):
    conn = MagicMock()
    conn.execute.return_value = _make_cursor(row=row, rows=rows)
    conn.cursor.return_value = _make_cursor(row=row, rows=rows)
    return conn


# Inject a stub for database.schema before importing app so create_tables is never called
_schema_stub = types.ModuleType('database.schema')
_schema_stub.create_tables = lambda: None
sys.modules.setdefault('database.schema', _schema_stub)

# Inject a stub pool so database.connection never dials MySQL
_mock_pool = MagicMock()
_mock_pool.get_connection.return_value = make_mock_conn()._connection

import database.connection as _conn_mod  # noqa: E402
_conn_mod._pool = _mock_pool  # inject before app imports the module


@pytest.fixture(scope='session')
def app():
    import app as app_module  # import after stubs are in place

    flask_app = app_module.app
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': None,
    })
    return flask_app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c
