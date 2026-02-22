# 1. Use an official Python runtime as a parent image (slim version for smaller image size)
FROM python:3.11-slim

# 2. Prevent Python from writing .pyc files and ensure output is sent directly to logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory in the container
WORKDIR /app

# 4. Install system dependencies (if needed)
# ffmpeg is used for audio processing, and build-essential is required for compiling any C extensions if needed by Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy the requirements file into the container
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the application code into the container
COPY . .

# 7. Expose the port that the FastAPI app will run on
EXPOSE 8000