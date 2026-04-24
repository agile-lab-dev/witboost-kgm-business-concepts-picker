FROM python:3.11-slim AS base

# Copy all necessary files.
WORKDIR /app
COPY README.md .
COPY pyproject.toml .
COPY poetry.lock .
COPY server_start.sh .
COPY application.yaml .

WORKDIR /app/src
COPY src/. .

# Install Poetry
RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --without dev

WORKDIR /app
RUN chmod +x server_start.sh

EXPOSE 5002

CMD ["./server_start.sh"]
