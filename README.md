# Projeto Flowter

Aplicacao Flask do Flowter para gerenciamento de escolas, turmas, disciplinas, professores e geracao de horarios.

## O que o projeto faz

- cadastro e login de usuarios
- verificacao de e-mail
- recuperacao de senha por link
- perfis de acesso: administrador, coordenador e funcionario
- vinculos de usuarios com escolas
- cadastro de escolas, turmas, disciplinas e professores
- geracao de horarios escolares

## Tecnologias

- Python 3.13+
- Flask
- MySQL 8+ ou MariaDB 10+
- `mysql-connector-python`

## Banco de dados

O projeto usa `MySQL` ou `MariaDB`.

Se o banco configurado em `DB_NAME` nao existir, a aplicacao tenta cria-lo automaticamente ao iniciar.
Para isso, o usuario configurado no banco precisa ter permissao para `CREATE DATABASE`.

As tabelas tambem sao criadas automaticamente na inicializacao.

Schema de referencia:

- `src/database/schema_mysql.sql`

## Configuracao local

Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Depois, preencha o `.env` com os dados do seu ambiente.

Exemplo seguro:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=app_user
DB_PASSWORD=change_me
DB_NAME=gestao_escolar

FLASK_SECRET_KEY=change_this_secret_key
FLASK_DEBUG=1
PORT=5000
APP_BASE_URL=http://localhost:5000

AUTH_BOOTSTRAP_ADMIN_NAME=Administrador
AUTH_BOOTSTRAP_ADMIN_EMAIL=
AUTH_BOOTSTRAP_ADMIN_PASSWORD=
AUTH_TEST_USER_NAME=Teste
AUTH_TEST_USER_EMAIL=teste@escola.com
AUTH_TEST_USER_PASSWORD=Teste12345
AUTH_ASSIGN_LEGACY_SCHOOLS_TO_EMAIL=

SESSION_COOKIE_SECURE=0
VERIFY_EMAIL_TOKEN_MAX_AGE=86400
RESET_PASSWORD_TOKEN_MAX_AGE=3600

MAIL_FROM_NAME=Flowter
MAIL_FROM_EMAIL=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=1
```

Observacoes:

- `APP_BASE_URL=http://localhost:5000` funciona para testes locais no mesmo computador.
- em producao, `APP_BASE_URL` deve ser a URL publica real da aplicacao, por exemplo `https://app.seudominio.com`
- nunca versione o `.env`

## Instalacao

Na raiz do projeto:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

No Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Como executar

Na raiz do projeto:

```bash
python3 src/app.py
```

No Windows:

```powershell
python src/app.py
```

## Fluxos de autenticacao

O sistema possui:

- cadastro de conta
- login
- reenvio de verificacao de e-mail
- recuperacao de senha
- redefinicao de senha por link

O usuario precisa confirmar o e-mail antes de entrar.

## Perfis e vinculos

O sistema agora trabalha com:

- `administrador`: acesso total, inclusive gestao de usuarios, perfis, vinculos e escolas
- `coordenador`: gerencia recursos e horarios apenas das escolas vinculadas
- `funcionario`: acesso de consulta e exportacao apenas das escolas vinculadas

Os vinculos sao armazenados na tabela `usuarios_escolas`.

Regras praticas:

- administradores podem acessar a tela `Usuarios`
- coordenadores e funcionarios so veem escolas com vinculo ativo
- funcionarios nao podem criar, editar ou remover dados escolares
- coordenadores podem editar dados e gerenciar horarios, mas nao usuarios globais

## E-mail com Gmail

O projeto suporta envio real de e-mail com Gmail usando SMTP.

Fluxos cobertos:

- verificacao de conta
- reenvio de verificacao
- recuperacao de senha

Exemplo de configuracao:

```env
APP_BASE_URL=http://localhost:5000
MAIL_FROM_NAME=Flowter
MAIL_FROM_EMAIL=seuemail@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seuemail@gmail.com
SMTP_PASSWORD=sua_senha_de_app_do_google
SMTP_USE_TLS=1
```

Importante:

- use senha de app do Google, nao a senha normal da conta
- `MAIL_FROM_EMAIL` e `SMTP_USER` normalmente devem ser o mesmo e-mail
- se o SMTP nao estiver configurado, os links sao registrados no log do servidor para testes locais
- se o SMTP estiver configurado e o envio falhar, a aplicacao registra o erro e informa o usuario

## Usuario administrador inicial

Se quiser criar automaticamente um usuario inicial na primeira subida, configure:

```env
AUTH_BOOTSTRAP_ADMIN_NAME=Administrador
AUTH_BOOTSTRAP_ADMIN_EMAIL=admin@escola.com
AUTH_BOOTSTRAP_ADMIN_PASSWORD=uma_senha_forte
```

Se o e-mail ainda nao existir, o usuario sera criado automaticamente.
Se ja existir, o perfil sera promovido para `administrador`.

## Usuario de teste fixo

A aplicacao mantem um usuario de teste verificado para facilitar testes locais:

```env
AUTH_TEST_USER_NAME=Teste
AUTH_TEST_USER_EMAIL=teste@escola.com
AUTH_TEST_USER_PASSWORD=Teste12345
```

Se esse usuario for excluido, ele sera criado novamente na proxima inicializacao da aplicacao.

## Publicacao em producao

Para publicar atras de `Nginx + HTTPS`, ajuste pelo menos:

```env
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1
APP_BASE_URL=https://app.seudominio.com
```

## Seguranca

- nao suba `.env` para o Git
- nao publique senhas de banco, SMTP ou senha de app do Google
- troque `FLASK_SECRET_KEY` por um valor forte em producao

## Arquivos importantes

- `src/app.py`: inicializacao da aplicacao
- `src/database/connection.py`: conexao com banco e criacao automatica do schema
- `src/database/schema.py`: criacao das tabelas
- `src/access_control.py`: regras de perfil e permissao
- `src/routes/auth_routes.py`: login, cadastro, verificacao e recuperacao de senha
- `src/routes/admin_routes.py`: gestao de usuarios e vinculos
- `src/email_service.py`: envio de e-mails

## Favicon

Para usar o icone do site, coloque a imagem em:

- `src/static/favicon/favicon.png`

Opcionalmente, se voce tiver um `.ico`, pode colocar tambem em:

- `src/static/favicon/favicon.ico`

## GitHub

Versione apenas arquivos seguros, como:

- codigo-fonte
- `README.md`
- `.env.example`
- arquivos de schema

Nao versione:

- `.env`
- `venv/`
- `__pycache__/`
- arquivos locais gerados durante testes
