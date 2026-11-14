FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/ezthing
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m -u 10001 appuser
USER appuser
ENV PORT=10000
# Liveness remains separate. Readiness validates database connectivity.
# Render may apply its own health check; this also helps other container hosts.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
 CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','10000')+'/api/ready',timeout=4).close()"
# Use exec so SIGTERM reaches uvicorn for graceful shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
