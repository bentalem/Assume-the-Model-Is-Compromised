FROM python:3.12-slim-bookworm

# Built exactly as the API is: dependencies from wheels vendored in the repository, with the package
# index disabled, so the build is reproducible and works without egress.
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1     PIP_NO_INDEX=1     PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY vendor/wheels /wheels
COPY services/memory/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY services/memory/pyproject.toml ./
COPY services/memory/src/ ./src/
# memory-init applies these. The service itself never reads them; they ship in one image so that the
# schema a service runs against is the schema its own build defined.
COPY database/memory/ /app/database/memory/
RUN pip install --no-index --find-links=/wheels --no-deps .  && rm -rf /wheels  && useradd --system --uid 10006 --no-create-home supportpilot

USER 10006
EXPOSE 8000
CMD ["supportpilot-memory"]
