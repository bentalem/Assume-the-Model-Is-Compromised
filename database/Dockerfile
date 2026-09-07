# Migration job. One-shot: applies forward migrations, runs smoke tests, exits.
FROM postgres:16.4-alpine

COPY migrations/ /migrations/
COPY seeds/      /seeds/
COPY tests/      /tests/
COPY entrypoint.sh /usr/local/bin/migrate.sh

RUN chmod +x /usr/local/bin/migrate.sh

USER postgres
ENTRYPOINT ["/usr/local/bin/migrate.sh"]
