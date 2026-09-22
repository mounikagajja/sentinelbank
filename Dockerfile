FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd --create-home --uid 1000 app

WORKDIR /app
RUN chown app:app /app
USER app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app alembic.ini ./
COPY --chown=app:app backend ./backend
COPY --chown=app:app ml ./ml
COPY --chown=app:app streaming ./streaming
COPY --chown=app:app assistant ./assistant
COPY --chown=app:app data ./data

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]