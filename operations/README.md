# Explicit database operations

These packages are outside every active Argo Application root. No operation ran
when the files were created. They are not deployment hooks.

After a configured platform handoff and reviewed image publication, the future
command `python -m automation.prepare_operation database-bootstrap` fills public
RDS metadata and the automation image digest. ALLOW_DATABASE_BOOTSTRAP remains
false; review the generated manifest, private secret values, TLS trust and current
DB ownership before explicitly authorizing it. The operation creates only the
five owner databases/roles and pinned vector extension; it does not seed app data.

For per-owner migration packages, use prepare_operation processing/business/drift/
knowledge after implementing the declared app migration module. These are proposed
entrypoints, not existing app modules. Each uses only its owner credential and the
app image digest. Run MLflow's managed DB upgrade separately with its MLflow image
and mlflow_db credential. Do not run every owner's migration at each Pod startup.

A reverse migration, role/password rotation and destructive schema cleanup require
separate reviewed procedures. Rollback of an image/model does not revert SQL.
Sensor PVC has Prune=false; training scratch uses a Delete storage class while
sensor/Kafka state uses Retain. Do not remove active state to clean up a deployment.
