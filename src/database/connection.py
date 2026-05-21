import logging
import os
import threading
from pathlib import Path
from typing import Any

import mysql.connector
import mysql.connector.pooling
from dotenv import load_dotenv
from mysql.connector import Error
from mysql.connector.errorcode import ER_BAD_DB_ERROR


LOGGER = logging.getLogger(__name__)
SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
DEFAULT_DB_PORT = 3306
_POOL_SIZE = 10

_pool: mysql.connector.pooling.MySQLConnectionPool | None = None
_pool_lock = threading.Lock()


def _load_environment() -> None:
    env_path = PROJECT_ROOT / '.env'
    load_dotenv(env_path, override=False)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(
            "Variaveis de ambiente ausentes para conexao com o banco: "
            f"{name}. Configure o arquivo .env ou as variaveis do sistema."
        )
    return value.strip()


def _get_database_config() -> dict[str, Any]:
    _load_environment()

    host = _get_required_env('DB_HOST')
    user = _get_required_env('DB_USER')
    password = _get_required_env('DB_PASSWORD')
    database = _get_required_env('DB_NAME')

    port_raw = os.getenv('DB_PORT', str(DEFAULT_DB_PORT)).strip()
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(
            "Valor invalido para DB_PORT. Informe uma porta numerica valida."
        ) from exc

    return {
        'host': host,
        'user': user,
        'password': password,
        'database': database,
        'port': port,
        'charset': 'utf8mb4',
        'use_unicode': True,
        'autocommit': False,
    }


def _server_connection_config(config: dict[str, Any]) -> dict[str, Any]:
    server_config = config.copy()
    server_config.pop('database', None)
    return server_config


def _create_database_if_missing(config: dict[str, Any]) -> None:
    connection = mysql.connector.connect(**_server_connection_config(config))
    cursor = connection.cursor()
    database_name = config['database']
    try:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _build_pool() -> mysql.connector.pooling.MySQLConnectionPool:
    config = _get_database_config()

    LOGGER.info(
        "Inicializando pool de conexoes MySQL (size=%d) em %s:%s, schema '%s'.",
        _POOL_SIZE,
        config['host'],
        config['port'],
        config['database'],
    )

    try:
        return mysql.connector.pooling.MySQLConnectionPool(
            pool_name="gestao_pool",
            pool_size=_POOL_SIZE,
            pool_reset_session=True,
            **config,
        )
    except Error as exc:
        if exc.errno == ER_BAD_DB_ERROR:
            LOGGER.warning(
                "Schema '%s' nao existe. Criando automaticamente.",
                config['database'],
            )
            try:
                _create_database_if_missing(config)
                return mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="gestao_pool",
                    pool_size=_POOL_SIZE,
                    pool_reset_session=True,
                    **config,
                )
            except Error as create_exc:
                raise RuntimeError(
                    "Nao foi possivel criar o banco MySQL/MariaDB automaticamente. "
                    "Verifique as permissoes do usuario configurado."
                ) from create_exc

        raise RuntimeError(
            "Erro ao conectar no banco MySQL/MariaDB. "
            "Verifique host, porta, usuario, senha e nome do banco."
        ) from exc


def _get_pool() -> mysql.connector.pooling.MySQLConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        _pool = _build_pool()
        return _pool


class DatabaseConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self, dictionary: bool = False):
        return self._connection.cursor(dictionary=dictionary, buffered=True)

    def execute(self, query: str, params: tuple[Any, ...] | None = None):
        cursor = self.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def get_connection() -> DatabaseConnection:
    try:
        return DatabaseConnection(_get_pool().get_connection())
    except Error as exc:
        raise RuntimeError(
            "Erro ao obter conexao do pool MySQL/MariaDB. "
            "Verifique se o banco esta acessivel e se o pool nao esta esgotado."
        ) from exc
