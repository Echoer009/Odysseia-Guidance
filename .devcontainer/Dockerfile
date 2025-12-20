FROM python:3.11.5-slim AS builder

# We no longer need to install gcc or mysql client, as our dependencies are pre-compiled.

WORKDIR /opt/pysetup

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --target /opt/pysetup/deps -r requirements.txt

FROM python:3.11.5-slim

WORKDIR /app

# We no longer need to install mysql client in the final image.

COPY --from=builder /opt/pysetup/deps /usr/local/lib/python3.11/site-packages

COPY . .

ENV PATH="/usr/local/lib/python3.11/site-packages/bin:${PATH}"

EXPOSE 80
