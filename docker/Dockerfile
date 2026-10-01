# Python-bot runtime. Download dependencies only at BUILD time.
FROM python:3.13-slim
WORKDIR /app
COPY requirements-upstreams.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY simulation/__init__.py simulation/contracts.py simulation/sdk.py simulation/registry.py simulation/worker.py /app/simulation/
COPY utils/ /app/utils/
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
USER 65534:65534
# No game configs, tournament secrets, results, or other bot directories copied.
# The supervisor mounts exactly one bot directory at runtime, read-only.
CMD ["python", "-m", "simulation.worker"]
