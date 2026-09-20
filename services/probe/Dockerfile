FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY vendor/wheels /wheels
COPY services/probe/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY services/probe/pyproject.toml ./
COPY services/probe/src/ ./src/
RUN pip install --no-index --find-links=/wheels --no-deps . \
 && rm -rf /wheels \
 && useradd --system --uid 10005 --no-create-home supportpilot

USER 10005
EXPOSE 8096
CMD ["supportpilot-probe"]
