FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN pip install --no-cache-dir . && playwright install --with-deps chromium

COPY docker/start-cron.sh /usr/local/bin/start-cron.sh
RUN chmod +x /usr/local/bin/start-cron.sh

ENTRYPOINT ["mloader"]
