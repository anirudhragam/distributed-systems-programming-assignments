FROM postgres:15

ENV POSTGRES_DB=customer_db
ENV POSTGRES_USER=customer_user
ENV POSTGRES_PASSWORD=customer_password

COPY init-schema.sql /docker-entrypoint-initdb.d/01-init-schema.sql

EXPOSE 5432
