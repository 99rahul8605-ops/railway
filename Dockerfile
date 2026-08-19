# Use official Python slim image
FROM python:3.11-slim

WORKDIR /app

# Install system deps (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for health check (Render requires a port)
EXPOSE 8000

# Healthcheck endpoint using a tiny HTTP server in background (optional)
# We'll run the bot directly; Render will keep the service alive.
CMD ["python", "main.py"]