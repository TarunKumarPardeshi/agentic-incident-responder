FROM python:3.12-slim

# Create non-root app user
RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY evals/ ./evals/

USER appuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.agent"]
