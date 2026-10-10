# Shared image definition for the FastAPI services.
# Build context is services/ so the shared pycommon package can be copied in:
#   docker build -f services/python.Dockerfile --build-arg SERVICE=product-service \
#                --build-arg PORT=8001 -t novasurge/product-service:local services
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# iproute2 provides `tc`, used by NovaSurge's latency_injection chaos experiment
# (the pod also needs the NET_ADMIN capability, granted in its manifest).
RUN apt-get update \
 && apt-get install -y --no-install-recommends iproute2 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-python.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ARG SERVICE
ARG PORT=8000
ENV PORT=${PORT}
COPY pycommon/ ./pycommon/
COPY ${SERVICE}/main.py ./main.py

EXPOSE ${PORT}
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --no-access-log --timeout-graceful-shutdown 5"]
