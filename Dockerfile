FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and documentation required for the build
COPY README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000
ENV HOST=0.0.0.0

EXPOSE 8000

CMD ["python", "-m", "bailian_gateway"]
