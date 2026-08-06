FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências da aplicação + gunicorn (servidor WSGI de produção)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Código-fonte
COPY src ./src

# app.py faz sys.path.insert(0, SRC_DIR); rodamos a partir de src/ com módulo "app:app"
WORKDIR /app/src

EXPOSE 5000

# create_tables() roda no import de app.py; o depends_on (healthy) garante o banco no ar.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "app:app"]
