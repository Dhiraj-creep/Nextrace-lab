FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY nextrace_lab /app/nextrace_lab
COPY services /app/services
COPY config /app/config

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
