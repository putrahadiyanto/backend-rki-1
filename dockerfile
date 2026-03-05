# STAGE 1: The Builder
FROM python:3.11-slim AS builder

WORKDIR /code

# Install build-essential only for the build phase
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install packages to a local folder to easily copy them later
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir --default-timeout=100 -r requirements.txt


# STAGE 2: The Final Runtime (Lightweight)
FROM python:3.11-slim

# Standard Python optimizations
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install ONLY ffmpeg (needed for your Groq/Audio tasks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled dependencies from the builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy app code
COPY . .

EXPOSE 8000