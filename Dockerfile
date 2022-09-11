FROM python:3.10.7-alpine3.16 as base

RUN apk update && \
    apk add --no-cache gcc musl-dev linux-headers python3-dev make libffi-dev openssl-dev g++ ca-certificates libtool m4 libuv-dev automake autoconf curl

RUN pip install -U pip
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/app/.venv/bin:/root/.local/bin:$PATH"

COPY ./dailybot/ /app/dailybot/
COPY ["pyproject.toml", "poetry.lock", "/app/"]

WORKDIR /app/
RUN POETRY_VIRTUALENVS_IN_PROJECT=true poetry install --no-dev --no-root --no-ansi --no-interaction

ENV PYTHONPATH="/app/dailybot:${PYTHONPATH}"

ENV PORT=3000 \
    LOG_LEVEL=DEBUG

EXPOSE 3000

CMD ["poetry", "run", "dailybot"]
