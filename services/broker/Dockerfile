FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies are installed from wheels vendored in the repository, with the package index
# disabled, exactly as the API is built.
COPY vendor/wheels /wheels
COPY services/broker/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY services/broker/pyproject.toml ./
COPY services/broker/src/ ./src/
RUN pip install --no-index --find-links=/wheels --no-deps . \
 && rm -rf /wheels \
 && useradd --system --uid 10007 --no-create-home supportpilot

USER 10007
EXPOSE 8097
CMD ["supportpilot-broker"]
