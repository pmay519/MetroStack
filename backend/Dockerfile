FROM python:3.11-slim

# 1. Install system dependencies for geometry libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libspatialindex-dev \
    libopenexr-dev \
    libtbb-dev \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Set up working directory and non-root user
WORKDIR /app
RUN useradd -m -u 1000 appuser

# 3. Create necessary directories and set ownership early
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

# 4. Install Python dependencies
# Doing this before copying the full app code leverages Docker's cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy application code with correct ownership
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser alembic.ini ./alembic.ini

# 6. Set environment variables
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 7. Switch to non-root user
USER appuser

# 8. Runtime configuration
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]