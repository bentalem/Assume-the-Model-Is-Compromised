FROM python:3.12-slim-bookworm

# Dependencies come from wheels vendored in the repository with the index disabled, like every
# other service here: reproducible, works without egress, and the artifact set is reviewable.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY vendor/wheels /wheels
COPY services/range/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY services/range/pyproject.toml ./
COPY services/range/src/ ./src/
RUN pip install --no-index --find-links=/wheels --no-deps . \
 && rm -rf /wheels \
 && useradd --system --uid 10004 --no-create-home supportpilot

# Challenge content is data. It is copied last so editing a challenge rebuilds one layer, and it
# lives outside the installed package so a bind mount can replace it during authoring.
COPY services/range/content/ /app/content/

USER 10004
EXPOSE 8095
CMD ["supportpilot-range"]
