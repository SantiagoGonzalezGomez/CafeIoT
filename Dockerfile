FROM python:3.12.7-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

COPY config ./config
COPY simulador ./simulador
ENV CAFE_DIR_CONFIG=/app/config
