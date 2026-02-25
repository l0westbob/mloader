FROM python:3.14-slim

WORKDIR /app

COPY . /app
RUN pip install --no-cache-dir . && playwright install --with-deps chromium

ENTRYPOINT ["mloader"]
