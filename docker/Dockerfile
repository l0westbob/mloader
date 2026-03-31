FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /bin/

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md response.proto .python-version /app/
COPY mloader /app/mloader
RUN uv sync --locked --no-dev \
    && uv run playwright install --with-deps chromium

COPY docker/start-cron.sh /usr/local/bin/start-cron.sh
RUN chmod +x /usr/local/bin/start-cron.sh

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT ["mloader"]
