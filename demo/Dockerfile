FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY traceforge_demo ./traceforge_demo

RUN pip install --no-cache-dir .
