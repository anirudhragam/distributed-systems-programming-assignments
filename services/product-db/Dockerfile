FROM postgres:15

ENV POSTGRES_DB=product_db
ENV POSTGRES_USER=product_user
ENV POSTGRES_PASSWORD=product_password

COPY init-schema.sql /docker-entrypoint-initdb.d/01-init-schema.sql

EXPOSE 5432
