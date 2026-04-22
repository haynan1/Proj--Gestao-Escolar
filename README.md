# Projeto Gestão Escolar

Aplicação Flask para gerenciamento de escolas, turmas, disciplinas, professores e geração de horários.

## Stack

- Python 3.13+
- Flask
- MySQL 8+ ou MariaDB 10+
- `mysql-connector-python`
- Autenticação por sessão com hash seguro de senha

## Banco de dados

O projeto está preparado para `MySQL` e `MariaDB`.

Crie o banco antes de iniciar a aplicação:

```sql
CREATE DATABASE gestao_escolar
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

O schema SQL de referência também está disponível em `src/database/schema_mysql.sql`.

## Configuração do ambiente

Crie seu arquivo local a partir do exemplo:

```bash
cp .env.example .env
```

Preencha as variáveis com os dados do seu ambiente:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=app_user
DB_PASSWORD=change_me
DB_NAME=gestao_escolar
FLASK_SECRET_KEY=change_this_secret_key
FLASK_DEBUG=1
PORT=5000
AUTH_BOOTSTRAP_ADMIN_NAME=Administrador
AUTH_BOOTSTRAP_ADMIN_EMAIL=
AUTH_BOOTSTRAP_ADMIN_PASSWORD=
AUTH_ASSIGN_LEGACY_SCHOOLS_TO_EMAIL=
SESSION_COOKIE_SECURE=0
VERIFY_EMAIL_TOKEN_MAX_AGE=86400
RESET_PASSWORD_TOKEN_MAX_AGE=3600
MAIL_FROM_NAME=EduSchedule
MAIL_FROM_EMAIL=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=1
```

O arquivo `.env` é apenas local e está ignorado no Git. O arquivo versionado no repositório deve ser somente o `.env.example`.

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Execução

```bash
python3 src/app.py
```

Ao iniciar, a aplicação cria automaticamente as tabelas definidas em `src/database/schema.py`.

## Autenticação

- O sistema agora exige login para acessar escolas, dashboards e horários.
- Novos usuários podem se cadastrar em `/cadastro`.
- O login usa proteção CSRF, bloqueio temporário após tentativas inválidas e sessão por cookie.
- A conta precisa confirmar o e-mail antes de entrar.
- Existem fluxos de `reenviar verificação`, `esqueci senha` e `redefinir senha`.
- As escolas ficam vinculadas ao usuário autenticado, isolando os dados por conta.
- Se quiser subir um usuário administrador inicial automaticamente, preencha:

```env
AUTH_BOOTSTRAP_ADMIN_NAME=Administrador
AUTH_BOOTSTRAP_ADMIN_EMAIL=admin@escola.com
AUTH_BOOTSTRAP_ADMIN_PASSWORD=uma_senha_forte
```

- Ao iniciar a aplicação, se esse e-mail ainda não existir, ele será criado.
- Para bases antigas, as escolas com `user_id` nulo não são mais atribuídas automaticamente ao primeiro usuário.
  Use `AUTH_ASSIGN_LEGACY_SCHOOLS_TO_EMAIL` se quiser fazer essa vinculação de forma explícita e segura.

## Configuração de e-mail

- Para produção, configure SMTP usando `MAIL_FROM_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_USE_TLS`.
- Em ambiente local sem SMTP configurado, os links de verificação e redefinição são registrados no log do servidor para teste.

## Preparando para o GitHub

- Confira se o `.env` não será versionado.
- Não suba arquivos gerados localmente, como `venv/`, `__pycache__/` e bancos `.db`.
- Se quiser publicar o projeto, basta versionar o código-fonte, o `README.md`, o `.env.example` e o schema SQL.
