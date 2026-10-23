FROM python:3.11-slim
LABEL org.opencontainers.image.title="LineSight" \
      org.opencontainers.image.authors="Kumar Waibhav Akshat <kwa.waibhav@gmail.com>" \
      org.opencontainers.image.description="CPU visual anomaly inspection with Isolation Forest"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LINESIGHT_ROOT=/app LINESIGHT_DB=/app/runtime/events.sqlite3
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY web ./web
COPY artifacts ./artifacts
COPY reports ./reports
RUN useradd --create-home --uid 10001 linesight && mkdir runtime && chown -R linesight:linesight /app
ENV PYTHONPATH=/app/src
USER linesight
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request,json; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health')); raise SystemExit(0 if r['model_loaded'] else 1)"
CMD ["python", "-m", "uvicorn", "linesight.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
