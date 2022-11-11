FROM python:3.9-slim

WORKDIR /

RUN pip3 install poetry

COPY poetry.lock /
COPY pyproject.toml /

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-dev --no-ansi

FROM python:3.9-slim

WORKDIR /

COPY --from=0 /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages

COPY klutch /klutch

ARG VERSION=dev

RUN sed -i "s/__version__ = .*/__version__ = '${VERSION}'/" /klutch/__init__.py

ENTRYPOINT ["python3", "-m", "klutch"]
