FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DATA_DIR=/app/harness/data \
    WORKSPACE=/app/harness/workspace \
    LOG_DIR=/app/harness/logs
WORKDIR /app
COPY . /app/harness
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/harness/data /app/harness/workspace /app/harness/logs \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3)"
CMD ["uvicorn", "harness.api:app", "--host", "0.0.0.0", "--port", "8000"]
