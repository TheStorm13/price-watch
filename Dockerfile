# syntax=docker/dockerfile:1

FROM python:3.14-slim-bookworm AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

CMD ["python", "main.py", "api", "--host", "0.0.0.0", "--port", "8000"]


FROM mcr.microsoft.com/playwright/python:v1.63.0-noble AS worker

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends novnc python3-venv websockify x11vnc \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DISPLAY=:99 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN chmod +x /app/docker/worker-entrypoint.sh \
    && mkdir -p /app/.playwright-profile \
    && chown -R pwuser:pwuser /app/.playwright-profile

USER pwuser

ENTRYPOINT ["/app/docker/worker-entrypoint.sh"]
CMD ["python", "main.py", "worker", "--profile-dir", "/app/.playwright-profile", "--browser-channel", "chromium", "--chrome-platform", "x11"]
