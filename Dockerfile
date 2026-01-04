# BIMFabrikHH API Dockerfile
# Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
# BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>

# ---- Base image ----
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    DOCKER_CONTAINER=true

# Install system dependencies (including GDAL for rasterio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    git \
    sed \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables for rasterio build
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# ---- Project setup stage ----
FROM base AS builder

WORKDIR /app

# Copy project files
COPY pyproject.toml poetry.lock* ./
COPY src ./src
COPY static ./static
COPY templates ./templates
COPY main.py ./
COPY env.example ./.env

# Configure Poetry to not create a virtualenv
RUN poetry config virtualenvs.create false

# Install dependencies (including from GitHub)
# Uses BuildKit secret to access private repos
RUN --mount=type=secret,id=github_token \
    git config --global url."https://$(cat /run/secrets/github_token)@github.com/".insteadOf "https://github.com/" && \
    poetry install --no-interaction --no-ansi --only main && \
    git config --global --unset url."https://$(cat /run/secrets/github_token)@github.com/".insteadOf


# ---- Final stage ----
FROM base AS final

WORKDIR /app

# Copy installed packages and source code from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /app /app

# Create necessary directories
RUN mkdir -p /app/logs /app/output /app/temp_files /app/database

# Set proper permissions
RUN chmod +x /app/main.py

# Expose port
EXPOSE 8083

# Set the default command 
CMD ["python", "main.py"]

