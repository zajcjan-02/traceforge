FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY traceforge ./traceforge
COPY alembic.ini .
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn traceforge.main:app --host 0.0.0.0 --port 8000"]
