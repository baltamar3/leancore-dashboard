FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts

RUN pip install --no-cache-dir .

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
