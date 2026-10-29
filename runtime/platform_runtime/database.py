"""Explicit day-zero operation; never an automatic startup hook."""
from __future__ import annotations

import json
import os
import re

import psycopg
from psycopg import sql

OWNERS={"processing":"processing_db","business":"business_db","drift":"drift_db","mlflow":"mlflow_db","knowledge":"knowledge_db"}


def main() -> None:
    if os.environ.get("ALLOW_DATABASE_BOOTSTRAP")!="true":
        raise ValueError("Explicit ALLOW_DATABASE_BOOTSTRAP=true required")
    parameters={"host":os.environ["PGHOST"],"port":int(os.environ.get("PGPORT","5432")),"dbname":"postgres","user":os.environ["PGUSER"],"password":os.environ["PGPASSWORD"],"sslmode":"verify-full","sslrootcert":os.environ["PGSSLROOTCERT"],"connect_timeout":10}
    vector_version=os.environ["PGVECTOR_VERSION"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",vector_version):raise ValueError("Pin pgvector extension version")
    with psycopg.connect(**parameters,autocommit=True) as connection:
        for owner,database in OWNERS.items():
            credential=json.loads(os.environ[owner.upper()+"_DATABASE_CREDENTIAL"])
            username=credential["username"]
            if not re.fullmatch(r"maintai_[a-z_]+",username):raise ValueError("Unexpected owner role name")
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(username,)).fetchone():
                connection.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION").format(sql.Identifier(username)))
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(username),sql.Literal(credential["password"])))
            if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s",(database,)).fetchone():
                connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database),sql.Identifier(username)))
            actual_owner = connection.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (database,)).fetchone()[0]
            if actual_owner != username:
                raise ValueError("Existing database owner differs; use an explicit ownership migration")
            connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
            connection.execute(sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(sql.Identifier(database),sql.Identifier(username)))
            with psycopg.connect(**{**parameters,"dbname":database},autocommit=True) as owned:
                owned.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                if owner=="knowledge":
                    owned.execute(sql.SQL("CREATE EXTENSION IF NOT EXISTS vector VERSION {}").format(sql.Literal(vector_version)))
                    installed=owned.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
                    if installed!=vector_version:raise ValueError("Installed vector version differs; explicit migration required")
    print("Five owner databases provisioned. Application migrations and MLflow migrations remain separate operations.")

if __name__=="__main__":main()
