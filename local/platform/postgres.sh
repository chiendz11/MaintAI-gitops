#!/bin/sh
set -eu
export PGHOST=postgres PGUSER=postgres PGDATABASE=postgres
export PGPASSWORD="$(cat /secrets/admin_password)"
for attempt in $(seq 1 90); do pg_isready -h postgres -U postgres >/dev/null 2>&1 && break; sleep 2; done
while read -r role database; do
  password="$(cat "/secrets/${role}_password")"
  psql -X -v ON_ERROR_STOP=1 -v role="$role" -v password="$password" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'role') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:'role') \gexec
SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'role', :'password') \gexec
SQL
done < /bootstrap/roles.tsv
for owner in processing business drift knowledge mlflow; do
  psql -X -v ON_ERROR_STOP=1 -v database="${owner}_db" -v owner="${owner}_owner" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'database', :'owner') WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname=:'database') \gexec
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'database') \gexec
SQL
done
while read -r role database; do
  psql -X -v ON_ERROR_STOP=1 -v role="$role" -v database="$database" <<'SQL'
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'database', :'role') \gexec
SQL
done < /bootstrap/roles.tsv
psql -X -v ON_ERROR_STOP=1 -d knowledge_db -c 'CREATE EXTENSION IF NOT EXISTS vector;'
echo 'Local database roles and five owner databases initialized; owner migrations/grants are separate.'
