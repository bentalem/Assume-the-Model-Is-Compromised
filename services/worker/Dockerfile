FROM python:3.12-slim-bookworm

# Dependencies are installed from wheels vendored in the repository, with the package index
# disabled. The build is reproducible, works without egress, and the exact artifact set is
# reviewable in version control (SP-BUILD-001 §10, provenance and dependency inventory).
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1     PIP_NO_INDEX=1     PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY vendor/wheels /wheels
COPY services/worker/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY services/worker/pyproject.toml ./
COPY services/worker/src/ ./src/
RUN pip install --no-index --find-links=/wheels --no-deps .  && rm -rf /wheels  && useradd --system --uid 10002 --no-create-home supportpilot

# Not root, and no build toolchain in the final image.
USER 10002

CMD ["supportpilot-worker"]
