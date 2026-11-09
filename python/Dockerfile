FROM python:3.12.14-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock.txt \
    && useradd --uid 10001 --create-home appuser
COPY main.py .
COPY agents ./agents
COPY config ./config
COPY models ./models
COPY orchestrator ./orchestrator
COPY services ./services
USER 10001
ENV PYTHONDONTWRITEBYTECODE=1 ECOM_LLM_MODE=offline
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
