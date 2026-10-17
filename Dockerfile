FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    CARBOT_STATE_PATH=/data/seen.sqlite

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY carbotfinder ./carbotfinder
RUN uv sync --frozen --no-dev

VOLUME ["/data"]
ENTRYPOINT ["uv", "run", "carbotfinder"]
CMD ["run", "-c", "/app/config.yaml", "--interval", "120", "-v"]
